import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiServerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_separates_agent_runners_and_model_connections(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["engine_ready"])
        self.assertEqual(payload["model_connection_policy"], "runner-managed")
        self.assertEqual(
            {item["runner_id"] for item in payload["agent_runners"]},
            {"opencode", "host-agent", "claude-code", "codex-cli"},
        )
        self.assertEqual(payload["model_connections"][0]["connection_id"], "opencode-starter")
        runners = self.client.get("/agent-runners").json()
        self.assertEqual(len(runners["items"]), 4)
        connections = self.client.get("/model-connections").json()
        self.assertEqual(connections["managed_by"], "agent-runner")

    def test_model_provider_disconnect_is_exposed_through_control_api(self):
        catalog = {
            "runner": "opencode",
            "selected_model": "opencode/big-pickle",
            "providers": [],
            "connected_provider_count": 0,
            "available_model_count": 0,
        }
        with patch("literary_engineering_studio.api_server.disconnect_provider", return_value=catalog) as disconnect:
            response = self.client.delete("/model-connections/opencode/credential/deepseek")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        disconnect.assert_called_once()
        self.assertEqual(disconnect.call_args.args[1], "deepseek")

    def test_frontend_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agent Studio", response.text)
        icon = self.client.get("/ui/assets/lucide/folder-kanban.svg")
        self.assertEqual(icon.status_code, 200)
        self.assertIn("<svg", icon.text)

    def test_desktop_token_is_exchanged_for_http_only_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = {
                "LES_API_TOKEN": "test-desktop-bootstrap-token",
                "LES_CONFIG_PATH": str(root / "config.json"),
                "LES_DATA_ROOT": str(root / "data"),
            }
            with patch.dict(os.environ, env):
                with TestClient(create_app()) as desktop:
                    self.assertEqual(desktop.get("/health").status_code, 401)
                    rejected = desktop.post(
                        "/desktop/session",
                        headers={"Authorization": "Bearer wrong-token"},
                    )
                    self.assertEqual(rejected.status_code, 401)
                    accepted = desktop.post(
                        "/desktop/session",
                        headers={"Authorization": "Bearer test-desktop-bootstrap-token"},
                    )
                    self.assertEqual(accepted.status_code, 200)
                    cookie = accepted.headers.get("set-cookie", "")
                    self.assertIn("HttpOnly", cookie)
                    self.assertIn("SameSite=strict", cookie)
                    self.assertEqual(desktop.get("/health").status_code, 200)

    def test_worker_stream_resumes_after_last_event_id(self):
        store = self.client.app.state.lifecycle.store
        job = store.create({"project_root": "C:/test", "route": "scene-development"})
        first = store.append_event(job["job_id"], "agent.text.delta", {"text": "第一段"})
        second = store.append_event(job["job_id"], "agent.text.delta", {"text": "第二段"})
        store.update(job["job_id"], status="complete", result={"status": "complete"})
        response = self.client.get(
            f"/worker/jobs/{job['job_id']}/stream",
            headers={"Last-Event-ID": str(first["sequence"])},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f"id: {first['sequence']}\n", response.text)
        self.assertIn(f"id: {second['sequence']}\n", response.text)
        self.assertIn("第二段", response.text)

    def test_delivery_center_lists_and_downloads_formal_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            (project / "exports").mkdir()
            artifact = project / "exports" / "final-manuscript.docx"
            artifact.write_bytes(b"test-docx")
            dashboard = {
                "route_audits": [
                    {
                        "route": "export-and-release",
                        "blocking_count": 0,
                        "pending_task_count": 0,
                        "top_blocking_gates": [],
                    }
                ]
            }
            with patch("literary_engineering_studio.delivery.build_dashboard", return_value=dashboard):
                response = self.client.get("/project/delivery", params={"project_root": str(project)})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["files"][0]["path"], "exports/final-manuscript.docx")

            download = self.client.get(
                "/project/delivery/download",
                params={"project_root": str(project), "path": "exports/final-manuscript.docx"},
            )
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.content, b"test-docx")

            rejected = self.client.get(
                "/project/delivery/download",
                params={"project_root": str(project), "path": "../project.yaml"},
            )
            self.assertEqual(rejected.status_code, 400)

    def test_project_client_can_create_select_and_record_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, {"LES_CONFIG_PATH": str(root / "studio" / "config.json")}):
                created = self.client.post(
                    "/projects/create",
                    json={
                        "parent_directory": str(root),
                        "title": "玻璃海岸",
                        "folder_name": "glass-coast",
                        "target_length": 200000,
                        "premise": "退潮后，城市会露出一条不存在于地图上的街道。",
                    },
                )
                self.assertEqual(created.status_code, 200)
                project = created.json()["project"]
                self.assertEqual(project["title"], "玻璃海岸")

                index = self.client.get("/projects")
                self.assertEqual(index.status_code, 200)
                self.assertEqual(index.json()["current_project"], project["path"])

                direction = self.client.post(
                    "/projects/directions",
                    json={"project_root": project["path"], "message": "先写日常秩序，再让异常逐步侵入。"},
                )
                self.assertEqual(direction.status_code, 200)
                history = self.client.get("/projects/directions", params={"project_root": project["path"]})
                self.assertEqual(history.json()["items"][0]["message"], "先写日常秩序，再让异常逐步侵入。")


if __name__ == "__main__":
    unittest.main()
