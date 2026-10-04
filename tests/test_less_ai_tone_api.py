import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from literary_engineering_studio.application.config import default_config, load_config
from literary_engineering_studio.api_server import create_app


class ToneApiTests(unittest.TestCase):
    def test_preferences_and_fresh_project_read_models(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "config.json"
            config = default_config()
            config["application"].update(data_root=str(directory / "data"),
                database_path=str(directory / "data/studio.sqlite3"), projects_root=str(directory / "projects"))
            with patch.dict(os.environ, {"LES_CONFIG_PATH": str(path)}), TestClient(create_app(config)) as client:
                response = client.get("/experiments/less-ai-tone")
                self.assertFalse(response.json()["preferences"]["enabled"])
                saved = client.put("/experiments/less-ai-tone", json={"enabled": True})
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertTrue(saved.json()["preferences"]["enabled"])
                self.assertTrue(load_config(path)["application"]["less_ai_tone_experiment"]["enabled"])
                self.assertEqual(client.put("/experiments/less-ai-tone", json={"enabled": "true"}).status_code, 422)
                created = client.post("/projects/create", json={"parent_directory": tmp, "folder_name": "tone-work",
                    "title": "自动编辑验收", "target_length": 5000, "premise": "一封信留在窗边。"})
                self.assertEqual(created.status_code, 200, created.text)
                params = {"project_root": created.json()["project"]["path"]}
                for endpoint in ("/health", "/projects", "/runtime/adapters", "/project/workspace"):
                    self.assertEqual(client.get(endpoint, params=params).status_code, 200, endpoint)
                stream = client.get("/project/workspace/stream", params={**params, "max_events": 1})
                self.assertEqual(stream.status_code, 200, stream.text)
                self.assertIn("event: workspace.snapshot", stream.text)
