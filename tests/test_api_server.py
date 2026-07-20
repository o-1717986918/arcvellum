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
