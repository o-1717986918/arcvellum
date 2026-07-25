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

    def test_controlled_asset_creation_previews_then_commits_without_accepting_paths(self):
        options = self.client.get(
            "/archive/creation/options",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(options.status_code, 200)
        character = next(
            item for item in options.json()["items"] if item["asset_type"] == "character"
        )
        content = str(character["template"]).replace("__ASSET_ID__", "mei")
        content = content.replace('name: ""', 'name: "梅汐"', 1)
        payload = {
            "project_root": str(self.root),
            "asset_type": "character",
            "local_id": "mei",
            "content": content,
            "semantic_review": "waived",
            "reason": "作者创建新的正式人物资产。",
        }
        preview = self.client.post("/archive/creation/preview", json=payload)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()["preview"]["committable"])
        committed = self.client.post(
            "/archive/creation/commit",
            json={
                **payload,
                "preview_digest": preview.json()["preview"]["preview_digest"],
            },
        )
        self.assertEqual(committed.status_code, 200)
        self.assertEqual(committed.json()["asset_id"], "character:mei")
        self.assertTrue((self.root / "characters" / "mei.yaml").is_file())
        self.assertNotIn(str(self.root), options.text)

        conflict = self.client.post(
            "/archive/creation/commit",
            json={
                **payload,
                "preview_digest": preview.json()["preview"]["preview_digest"],
            },
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "asset_creation_conflict")

        invalid = self.client.post(
            "/archive/creation/preview",
            json={
                **payload,
                "local_id": "../outside",
                "content": content.replace("mei", "../outside"),
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["detail"]["code"], "creation_validation")

    def test_history_rebuild_and_restore_preview_never_mutate_the_asset(self):
        detail = self.client.get(
            "/archive/assets/character:lin",
            params={"project_root": str(self.root)},
        ).json()
        original_revision = detail["asset"]["revision"]
        original_content = detail["asset"]["content"]
        committed = self.client.post(
            "/archive/assets/character:lin/commit",
            json={
                "project_root": str(self.root),
                "base_revision": original_revision,
                "content": "character_id: lin\nname: 林澈\nimportance: secondary\n",
                "semantic_review": "waived",
                "reason": "作者明确调整角色权重。",
            },
        )
        self.assertEqual(committed.status_code, 200)
        changed = (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8")

        history = self.client.get(
            "/archive/assets/character:lin/history",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(history.status_code, 200)
        revisions = {item["revision"] for item in history.json()["revisions"]}
        self.assertIn(original_revision, revisions)
        self.assertIn(committed.json()["receipt"]["new_revision"], revisions)

        preview = self.client.post(
            "/archive/assets/character:lin/restore/preview",
            json={
                "project_root": str(self.root),
                "revision": original_revision,
                "reason": "作者预览恢复最初人物设定。",
            },
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["restore"]["revision"], original_revision)
        self.assertEqual(preview.json()["preview"]["transaction"]["patch"][0]["value"], original_content)
        self.assertEqual((self.root / "characters" / "lin.yaml").read_text(encoding="utf-8"), changed)

    def test_recycle_bin_api_archives_and_restores_by_stable_ids(self):
        (self.root / "characters" / "mei.yaml").write_text(
            "character_id: mei\nname: 梅汐\nimportance: secondary\n",
            encoding="utf-8",
        )
        detail = self.client.get(
            "/archive/assets/character:mei",
            params={"project_root": str(self.root)},
        ).json()
        archived = self.client.post(
            "/archive/assets/character:mei/archive",
            json={
                "project_root": str(self.root),
                "base_revision": detail["asset"]["revision"],
                "reason": "作者暂时归档未使用人物。",
            },
        )
        self.assertEqual(archived.status_code, 200)
        entry_id = archived.json()["receipt"]["entry_id"]
        self.assertFalse((self.root / "characters" / "mei.yaml").exists())

        recycle = self.client.get(
            "/archive/recycle-bin",
            params={"project_root": str(self.root)},
        )
        self.assertEqual(recycle.status_code, 200)
        self.assertEqual(recycle.json()["items"][0]["entry_id"], entry_id)
        self.assertNotIn(str(self.root), recycle.text)

        restored = self.client.post(
            "/archive/assets/character:mei/restore",
            json={
                "project_root": str(self.root),
                "entry_id": entry_id,
                "reason": "作者恢复人物继续开发。",
            },
        )
        self.assertEqual(restored.status_code, 200)
        self.assertTrue((self.root / "characters" / "mei.yaml").is_file())

    def test_structured_editor_api_uses_registered_fields_and_stable_errors(self):
        content = (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8")
        structured = self.client.post(
            "/archive/assets/character:lin/structure",
            json={"project_root": str(self.root), "content": content},
        )
        self.assertEqual(structured.status_code, 200)
        source_revision = structured.json()["source_revision"]
        self.assertIn(
            "name",
            {field["name"] for field in structured.json()["fields"]},
        )

        rendered = self.client.post(
            "/archive/assets/character:lin/render-structured",
            json={
                "project_root": str(self.root),
                "content": content,
                "source_revision": source_revision,
                "fields": {"name": "林汐"},
            },
        )
        self.assertEqual(rendered.status_code, 200)
        self.assertIn("name: 林汐", rendered.json()["content"])
        self.assertEqual(
            (self.root / "characters" / "lin.yaml").read_text(encoding="utf-8"),
            content,
        )

        forbidden = self.client.post(
            "/archive/assets/character:lin/render-structured",
            json={
                "project_root": str(self.root),
                "content": content,
                "source_revision": source_revision,
                "fields": {"character_id": "other"},
            },
        )
        self.assertEqual(forbidden.status_code, 400)
        self.assertEqual(
            forbidden.json()["detail"]["code"],
            "structured_field_invalid",
        )

        stale = self.client.post(
            "/archive/assets/character:lin/render-structured",
            json={
                "project_root": str(self.root),
                "content": content + "\n",
                "source_revision": source_revision,
                "fields": {"name": "林汐"},
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "structured_draft_stale")


if __name__ == "__main__":
    unittest.main()
