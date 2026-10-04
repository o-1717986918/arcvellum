"""Fresh work through real composition, HTTP contracts and read/SSE surfaces."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio.application.container import build_application_container
from literary_engineering_studio.infrastructure.defaults import build_default_application_ports


class StylometryApiTests(unittest.TestCase):
    def test_fresh_project_statistics_preview_mount_measure_and_unmount(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"LES_CONFIG_PATH": str(Path(tmp) / "config.json")}):
            directory, config = Path(tmp), default_config()
            config["application"].update(data_root=str(directory / "data"), database_path=str(directory / "data/db.sqlite3"),
                                         projects_root=str(directory / "projects"))
            container = build_application_container(config, build_default_application_ports(config))
            with TestClient(create_app(container=container)) as client:
                root = client.post("/projects/create", json={"parent_directory": str(directory), "folder_name": "work",
                    "title": "计量文风验收", "target_length": 5000, "premise": "一封信留在窗边。"}).json()["project"]["path"]
                params = {"project_root": root}
                for endpoint in ("/health", "/projects", "/runtime/adapters"):
                    self.assertEqual(client.get(endpoint).status_code, 200)
                self.assertEqual(client.get("/project/workspace", params=params).status_code, 200)
                stream = client.get("/project/workspace/stream", params={**params, "max_events": 1})
                self.assertIn("event: workspace.snapshot", stream.text)
                self.assertFalse(client.get("/stylometry/workbench", params=params).json()["mount"]["enabled"])
                profile = client.post("/stylometry/analyze", json={**params, "title": "河与山", "sources": [
                    {"source_id": "train-one", "work_id": "work-one", "text": "风从河面吹来。她把门推开，看看炉中的火。" * 30},
                    {"source_id": "holdout-one", "work_id": "work-two", "split": "holdout",
                     "text": "他循着山路走过去。石头上落着水，远处传来鸟叫。" * 30}]}).json()
                request = {**params, "profile_id": profile["profile_id"], "controls_json": json.dumps(profile["controls"]), "title": "舒缓"}
                preview = client.post("/stylometry/compile", json=request)
                self.assertEqual(preview.status_code, 200, preview.text)
                version = client.post("/stylometry/versions", json={**request, "fragment_override": "让句子的呼吸顺着风展开。"}).json()
                mounted = client.post("/stylometry/mount", json={**params, "version_id": version["version_id"],
                    "enabled": True, "expected_revision": 0})
                self.assertEqual(mounted.status_code, 200, mounted.text)
                report = client.post("/stylometry/measure", json={**params, "version_id": version["version_id"], "text": "雨停了。窗子开着。"})
                self.assertTrue(report.json()["targets"])
                self.assertEqual(client.post("/stylometry/mount", json={**params, "enabled": False, "expected_revision": 0}).status_code, 400)
                self.assertFalse(client.post("/stylometry/mount", json={**params, "enabled": False, "expected_revision": 1}).json()["enabled"])
                request["controls_json"] = "{}"
                self.assertEqual(client.post("/stylometry/compile", json=request).status_code, 400)
            container.shutdown()
