from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.assets.loader import AssetLoader
from literary_engineering_studio.application.assets.recycle_bin import (
    ArchiveReferenceConflictError,
    RecycleBinService,
    RestoreConflictError,
)
from literary_engineering_studio.application.assets.registry import AssetViewRegistry
from literary_engineering_studio.jobs import JobStore


class ArchiveRecycleBinTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
        (self.root / "characters").mkdir()
        (self.root / "characters" / "lin.yaml").write_text(
            "character_id: lin\nname: 林澈\nimportance: major\n",
            encoding="utf-8",
        )
        (self.root / "characters" / "mei.yaml").write_text(
            "character_id: mei\nname: 梅汐\nimportance: secondary\n",
            encoding="utf-8",
        )
        (self.root / "scenes").mkdir()
        (self.root / "scenes" / "scene_0001.yaml").write_text(
            "scene_id: scene_0001\nchapter_id: chapter_0001\nparticipant_refs: [lin]\n",
            encoding="utf-8",
        )
        self.registry = AssetViewRegistry.default()
        self.loader = AssetLoader(self.registry)

    def tearDown(self):
        self.temporary.cleanup()

    def test_formal_reference_blocks_archive_even_for_owner(self):
        service = RecycleBinService(self.registry, self.loader)
        asset = self.loader.load(self.root, "character:lin")

        with self.assertRaises(ArchiveReferenceConflictError) as caught:
            service.archive(
                self.root,
                "character:lin",
                base_revision=asset.revision,
                reason="作者尝试归档仍被场景引用的人物。",
            )

        self.assertIn("scenes/scene_0001.yaml", caught.exception.blockers)
        self.assertTrue((self.root / "characters" / "lin.yaml").is_file())

    def test_archive_and_restore_preserve_snapshot_and_rebuild_index(self):
        service = RecycleBinService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:mei")

        archived = service.archive(
            self.root,
            "character:mei",
            base_revision=before.revision,
            reason="作者暂时移出未进入正式剧情的人物。",
        )

        with self.assertRaises(FileNotFoundError):
            self.loader.load(self.root, "character:mei")
        entry_id = archived["entry_id"]
        entry_file = self.root / archived["entry_path"]
        self.assertTrue(entry_file.is_file())
        snapshot = self.root / archived["snapshot_path"]
        self.assertEqual(snapshot.read_text(encoding="utf-8"), before.content)

        store = JobStore(Path(self.temporary.name) / "recycle.sqlite3")
        restarted = RecycleBinService(self.registry, self.loader, store)
        entries = restarted.entries(self.root)
        self.assertEqual(entries["synchronization"]["indexed"], 1)
        self.assertEqual(entries["items"][0]["entry_id"], entry_id)
        self.assertEqual(entries["items"][0]["status"], "active")

        restored = restarted.restore(
            self.root,
            "character:mei",
            entry_id=entry_id,
            reason="作者恢复人物并继续开发。",
        )

        self.assertEqual(restored["status"], "restored")
        self.assertEqual(self.loader.load(self.root, "character:mei").content, before.content)
        self.assertTrue(snapshot.is_file(), "immutable recycle snapshot must remain as history")
        self.assertEqual(restarted.entries(self.root)["items"][0]["status"], "restored")

    def test_archive_and_restore_failures_roll_back_formal_path(self):
        service = RecycleBinService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:mei")
        with patch(
            "literary_engineering_studio.application.assets.recycle_bin._activate_entry",
            side_effect=RuntimeError("activation failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "activation failed"):
                service.archive(
                    self.root,
                    "character:mei",
                    base_revision=before.revision,
                    reason="测试归档激活失败回滚。",
                )
        self.assertEqual(self.loader.load(self.root, "character:mei").revision, before.revision)

        archived = service.archive(
            self.root,
            "character:mei",
            base_revision=before.revision,
            reason="为恢复失败测试准备归档。",
        )
        with patch(
            "literary_engineering_studio.application.assets.recycle_bin._mark_restored",
            side_effect=RuntimeError("restore receipt failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "restore receipt failed"):
                service.restore(
                    self.root,
                    "character:mei",
                    entry_id=archived["entry_id"],
                    reason="测试恢复回执失败回滚。",
                )
        with self.assertRaises(FileNotFoundError):
            self.loader.load(self.root, "character:mei")

    def test_restore_rejects_existing_formal_target(self):
        service = RecycleBinService(self.registry, self.loader)
        before = self.loader.load(self.root, "character:mei")
        archived = service.archive(
            self.root,
            "character:mei",
            base_revision=before.revision,
            reason="为冲突测试准备归档。",
        )
        (self.root / "characters" / "mei.yaml").write_text(
            "character_id: mei\nname: 新梅汐\n",
            encoding="utf-8",
        )

        with self.assertRaises(RestoreConflictError):
            service.restore(
                self.root,
                "character:mei",
                entry_id=archived["entry_id"],
                reason="不能覆盖归档后新建的同名人物。",
            )


if __name__ == "__main__":
    unittest.main()
