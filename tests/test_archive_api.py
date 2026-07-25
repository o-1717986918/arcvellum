from pathlib import Path
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ArchiveApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        data = Path(self.temporary.name)
        self.root = data / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
        (self.root / "characters").mkdir()
        (self.root / "characters" / "lin.yaml").write_text(
            "character_id: lin\nname: 林澈\nimportance: major\n",
            encoding="utf-8",
        )
        config = default_config()
        config["application"]["data_root"] = str(data / "data")
        config["application"]["database_path"] = str(data / "data" / "studio.sqlite3")
        config["application"]["projects_root"] = str(data)
        config["worker"]["runs_root"] = str(data / "runs")
        config["agent_runners"]["opencode"]["data_root"] = str(data / "data")
        self.client = TestClient(create_app(config))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_archive_read_validate_impact_and_commit_use_stable_asset_identity(self):
        tree = self.client.get("/archive/tree", params={"project_root": str(self.root)})
        self.assertEqual(tree.status_code, 200)
        self.assertNotIn(str(self.root), tree.text)

        detail = self.client.get(
            "/archive/assets/character:lin",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(detail.status_code, 200)
        revision = detail.json()["asset"]["revision"]

        invalid = self.client.post(
            "/archive/assets/character:lin/validate",
            json={"project_root": str(self.root), "content": "character_id: other\nname: 林澈\n"},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(invalid.json()["validation"]["valid"])

        impact = self.client.post(
            "/archive/assets/character:lin/impact",
            json={
                "project_root": str(self.root),
                "content": "character_id: lin\nname: 林澈\nimportance: secondary\n",
            },
        )
        self.assertEqual(impact.status_code, 200)
        self.assertIn("summary", impact.json()["impact"])

        committed = self.client.post(
            "/archive/assets/character:lin/commit",
            json={
                "project_root": str(self.root),
                "base_revision": revision,
                "content": "character_id: lin\nname: 林澈\nimportance: secondary\n",
                "semantic_review": "waived",
                "reason": "作者明确调整角色权重。",
            },
        )
        self.assertEqual(committed.status_code, 200)
        self.assertEqual(committed.json()["receipt"]["authority"], "owner")

        stale = self.client.post(
            "/archive/assets/character:lin/commit",
            json={
                "project_root": str(self.root),
                "base_revision": revision,
                "content": "character_id: lin\nname: 林澈\nimportance: major\n",
                "semantic_review": "waived",
                "reason": "模拟旧标签页覆盖。",
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "version_conflict")


if __name__ == "__main__":
    unittest.main()
