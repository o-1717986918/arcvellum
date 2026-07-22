import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.config = default_config()
        self.config["application"]["data_root"] = str(root)
        self.config["application"]["database_path"] = str(root / "studio.sqlite3")
        self.config["application"]["projects_root"] = str(root / "projects")
        self.config["worker"]["runs_root"] = str(root / "runs")
        self.config["agent_runners"]["opencode"]["data_root"] = str(root)
        self.client = TestClient(create_app(self.config))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_health_separates_agent_runners_and_model_connections(self):
        self.client.app.state.bootstrap._engine_future.result(timeout=15)
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

    def test_bootstrap_endpoint_defers_model_catalog_until_settings(self):
        service = self.client.app.state.bootstrap
        service._catalog_loader = lambda _config: {
            "runner": "opencode",
            "selected_model": "opencode/example-model",
            "providers": [],
            "connected_provider_count": 1,
            "available_model_count": 1,
        }
        service._engine_future.result(timeout=15)
        response = self.client.get("/application/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["can_enter_workspace"])
        self.assertEqual(payload["schema"], "arcvellum/application-bootstrap/v0.1")
        self.assertEqual(payload["model_warmup"]["status"], "deferred")

    def test_bootstrap_stream_uses_named_sse_event(self):
        service = self.client.app.state.bootstrap
        service._catalog_loader = lambda _config: {
            "providers": [],
            "available_model_count": 0,
        }
        response = self.client.get(
            "/application/bootstrap/stream",
            params={"interval_seconds": 1, "max_events": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: application.bootstrap", response.text)
        self.assertIn("can_enter_workspace", response.text)

    def test_help_details_and_legal_are_real_product_endpoints(self):
        details = self.client.get("/application/details")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["product_name"], "ArcVellum")
        self.assertTrue(details.json()["repository_url"].endswith("/arcvellum"))

        help_center = self.client.get("/help")
        self.assertEqual(help_center.status_code, 200)
        self.assertGreaterEqual(len(help_center.json()["topics"]), 5)

        legal = self.client.get("/application/legal")
        self.assertEqual(legal.status_code, 200)
        self.assertEqual({item["id"] for item in legal.json()["documents"]}, {"terms", "privacy", "third-party"})

    def test_narrative_stream_emits_sequence_and_delta(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            projection = {
                "ok": True,
                "schema": "arcvellum/narrative-projection/v2",
                "revision": "revision-one",
                "nodes": [],
                "edges": [],
                "timeline": [],
                "summary": {},
            }
            with patch("literary_engineering_studio.api_server.build_narrative_projection", return_value=projection):
                response = self.client.get(
                    "/narrative/stream",
                    params={"project_root": str(root), "max_events": 1, "interval_seconds": 2},
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: narrative.projection", response.text)
            self.assertIn("id: 1", response.text)
            self.assertIn('"initial": true', response.text)

    def test_narrative_v3_exposes_spatial_contract_and_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            projection = {
                "ok": True,
                "schema": "arcvellum/narrative-projection/v3",
                "revision": "spatial-revision-one",
                "nodes": [],
                "edges": [],
                "timeline": [],
                "summary": {},
                "source_revisions": {},
            }
            with patch("literary_engineering_studio.api_server.build_narrative_projection_v3", return_value=projection):
                snapshot = self.client.get("/narrative/projection/v3", params={"project_root": str(root), "grammar": "braid"})
                self.assertEqual(snapshot.status_code, 200)
                self.assertEqual(snapshot.json()["schema"], "arcvellum/narrative-projection/v3")
                stream = self.client.get(
                    "/narrative/stream/v3",
                    params={"project_root": str(root), "grammar": "braid", "max_events": 1, "interval_seconds": 2},
                )
            self.assertEqual(stream.status_code, 200)
            self.assertIn("event: narrative.v3.projection", stream.text)
            self.assertIn("id: 1", stream.text)

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
        self.assertIn("ArcVellum", response.text)
        self.assertIn("/ui/assets/", response.text)
        script_path = re.search(r'<script[^>]+src="([^"]+)"', response.text).group(1)
        stylesheet_path = re.search(r'<link[^>]+href="([^"]+\.css)"', response.text).group(1)
        self.assertEqual(self.client.get(script_path).status_code, 200)
        self.assertEqual(self.client.get(stylesheet_path).status_code, 200)
        legacy = self.client.get("/legacy")
        self.assertEqual(legacy.status_code, 404)

    def test_desktop_token_is_exchanged_for_http_only_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = {
                "LES_API_TOKEN": "test-desktop-bootstrap-token",
                "LES_CONFIG_PATH": str(root / "config.json"),
                "LES_DATA_ROOT": str(root / "data"),
            }
            with patch.dict(os.environ, env):
                with TestClient(create_app(self.config)) as desktop:
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

    def test_packaged_tauri_origin_can_send_authenticated_cross_origin_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = {
                "LES_API_TOKEN": "test-desktop-bootstrap-token",
                "LES_CONFIG_PATH": str(root / "config.json"),
                "LES_DATA_ROOT": str(root / "data"),
            }
            with patch.dict(os.environ, env):
                with TestClient(create_app(self.config)) as desktop:
                    response = desktop.options(
                        "/application/bootstrap",
                        headers={
                            "Origin": "http://tauri.localhost",
                            "Access-Control-Request-Method": "GET",
                            "Access-Control-Request-Headers": "authorization",
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers.get("access-control-allow-origin"), "http://tauri.localhost")
                    self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")
                    patch_response = desktop.options(
                        "/project/display-field",
                        headers={
                            "Origin": "http://tauri.localhost",
                            "Access-Control-Request-Method": "PATCH",
                            "Access-Control-Request-Headers": "authorization,content-type",
                        },
                    )
                    self.assertEqual(patch_response.status_code, 200)
                    self.assertIn("PATCH", patch_response.headers.get("access-control-allow-methods", ""))

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
            with patch("literary_engineering_studio.api_server.build_dashboard", return_value=dashboard):
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

    def test_delivery_stream_publishes_real_delivery_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            (project / "exports").mkdir()
            (project / "exports" / "final-manuscript.docx").write_bytes(b"test-docx")
            dashboard = {
                "route_audits": [{
                    "route": "export-and-release",
                    "blocking_count": 0,
                    "pending_task_count": 0,
                    "top_blocking_gates": [],
                }]
            }
            with patch("literary_engineering_studio.api_server.build_dashboard", return_value=dashboard):
                response = self.client.get(
                    "/project/delivery/stream",
                    params={"project_root": str(project), "max_events": 1},
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: delivery", response.text)
            self.assertIn("final-manuscript.docx", response.text)

    def test_workspace_stream_coalesces_project_read_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            (project / "exports").mkdir()
            (project / "exports" / "final-manuscript.docx").write_bytes(b"test-docx")
            dashboard = {
                "route_audits": [{
                    "route": "export-and-release",
                    "blocking_count": 0,
                    "pending_task_count": 0,
                    "top_blocking_gates": [],
                }]
            }
            with patch("literary_engineering_studio.api_server.build_dashboard", return_value=dashboard):
                response = self.client.get(
                    "/project/workspace/stream",
                    params={"project_root": str(project), "max_events": 1},
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: workspace.snapshot", response.text)
            self.assertIn('"dashboard"', response.text)
            self.assertIn('"reader_manifest"', response.text)
            self.assertIn('"agent_observability"', response.text)

    def test_workspace_snapshot_hydrates_read_models_in_one_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            dashboard = {
                "route_audits": [{
                    "route": "export-and-release",
                    "blocking_count": 0,
                    "pending_task_count": 0,
                    "top_blocking_gates": [],
                }]
            }
            with patch("literary_engineering_studio.api_server.build_dashboard", return_value=dashboard):
                response = self.client.get("/project/workspace", params={"project_root": str(project)})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertIn("dashboard", payload)
            self.assertIn("library", payload)
            self.assertIn("reader_manifest", payload)

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

                choice = self.client.post(
                    "/workflow/human-choice",
                    json={
                        "project_root": project["path"],
                        "choice_id": "choice-api-budget",
                        "route": "longform-planning",
                        "decision_type": "word_budget_direction",
                        "target": {"target_id": "volume_01"},
                        "options": [{"id": "expand_inventory", "label": "扩充剧情库存"}],
                        "selected": "expand_inventory",
                        "rationale": "先增加剧情事件，再安排章节预算。",
                        "actor": "arcvellum-user",
                    },
                )
                self.assertEqual(choice.status_code, 200)
                self.assertEqual(choice.json()["effect"]["kind"], "creative-direction")
                history = self.client.get("/projects/directions", params={"project_root": project["path"]})
                self.assertIn("expand_inventory", history.json()["items"][-1]["message"])

    def test_autopilot_policy_is_user_configurable_and_persistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            current = self.client.get("/autopilot/status", params={"project_root": str(project)})
            self.assertEqual(current.status_code, 200)
            policy = current.json()["policy"]
            policy["mode"] = "supervised_auto"
            policy["delegated_decisions"] = ["branch_selection"]
            saved = self.client.put("/autopilot/policy", json={"project_root": str(project), "policy": policy})
            self.assertEqual(saved.status_code, 200)
            loaded = self.client.get("/autopilot/status", params={"project_root": str(project)}).json()
            self.assertEqual(loaded["policy"]["mode"], "supervised_auto")
            self.assertEqual(loaded["policy"]["delegated_decisions"], ["branch_selection"])

            policy["mode"] = "full_auto"
            policy["release_policy"] = "delegated"
            self.client.put("/autopilot/policy", json={"project_root": str(project), "policy": policy})
            blocked = self.client.post(
                "/autopilot/start",
                json={"project_root": str(project), "runtime": "opencode", "authorized": False},
            )
            self.assertEqual(blocked.status_code, 400)
            self.assertIn("明确确认授权", blocked.json()["detail"])

    def test_advisor_stream_separates_visible_text_from_final_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            session = self.client.post("/advisor/sessions", json={"project_root": str(project)}).json()

            def fake_ask(_advisor, _session_id, _question, **kwargs):
                kwargs["event_sink"]("advisor.delta", {"text": "自然回答"})
                return {"schema": "arcvellum/advisor-answer/v0.2", "message": "自然回答", "evidence": [], "uncertainties": [], "suggested_actions": []}

            with patch("literary_engineering_studio.advisor.ProjectAdvisor.ask", new=fake_ask):
                response = self.client.post(
                    f"/advisor/sessions/{session['session_id']}/ask/stream",
                    json={"question": "现在应该关注什么？"},
                )
            self.assertEqual(response.status_code, 200)
            self.assertIn("event: advisor.delta", response.text)
            self.assertIn("自然回答", response.text)
            self.assertIn("event: advisor.result", response.text)
            self.assertLess(response.text.index("event: advisor.delta"), response.text.index("event: advisor.result"))

    def test_advisor_stream_paces_a_coarse_provider_delta_without_changing_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / "project.yaml").write_text("title: test\n", encoding="utf-8")
            session = self.client.post("/advisor/sessions", json={"project_root": str(project)}).json()
            answer = "先处理人物选择与代价，让下一场有明确承接。随后检查章节张力是否经历蓄势、峰值和回落，而不是连续维持同一种速度。"

            def fake_ask(_advisor, _session_id, _question, **kwargs):
                kwargs["event_sink"]("advisor.delta", {"text": answer})
                return {"schema": "arcvellum/advisor-answer/v0.2", "message": answer, "evidence": [], "uncertainties": [], "suggested_actions": []}

            with patch("literary_engineering_studio.advisor.ProjectAdvisor.ask", new=fake_ask):
                response = self.client.post(
                    f"/advisor/sessions/{session['session_id']}/ask/stream",
                    json={"question": "现在应该关注什么？"},
                )
            delta_payloads = []
            current_event = ""
            for line in response.text.splitlines():
                if line.startswith("event: "):
                    current_event = line.removeprefix("event: ")
                elif current_event == "advisor.delta" and line.startswith("data: "):
                    delta_payloads.append(json.loads(line.removeprefix("data: ")))
            self.assertGreater(len(delta_payloads), 1)
            self.assertEqual("".join(str(item["text"]) for item in delta_payloads), answer)


if __name__ == "__main__":
    unittest.main()
