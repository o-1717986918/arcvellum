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

    def test_health_exposes_agent_runtimes_without_model_provider(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["engine_ready"])
        self.assertEqual(payload["model_provider"], "disabled-by-architecture")
        self.assertEqual({item["runtime"] for item in payload["runtimes"]}, {"host-agent", "claude-code", "codex-cli"})

    def test_frontend_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agent Studio", response.text)
        icon = self.client.get("/ui/assets/lucide/folder-kanban.svg")
        self.assertEqual(icon.status_code, 200)
        self.assertIn("<svg", icon.text)

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
