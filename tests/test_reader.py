from pathlib import Path
import json
import tempfile
import time
import unittest

from literary_engineering_studio.reader import build_reader_manifest, public_reader_manifest, read_reader_unit, search_reader
from literary_engineering_studio.jobs import JobStore


class ReaderProjectionTests(unittest.TestCase):
    def test_reader_position_and_bookmarks_survive_restart_without_storing_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            store.save_reader_position("C:/work", "chapter_0001.scene_0002", 0.42)
            store.set_reader_bookmark("C:/work", "chapter_0001.scene_0001", True)
            restarted = JobStore(database)
            state = restarted.reader_state("C:/work")
            self.assertEqual(state["position"]["unit_id"], "chapter_0001.scene_0002")
            self.assertAlmostEqual(state["position"]["scroll_ratio"], 0.42)
            self.assertEqual(state["bookmarks"][0]["unit_id"], "chapter_0001.scene_0001")

    def test_promoted_scenes_are_ordered_and_return_full_clean_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_project(root)
            _scene(root, "scene_0002", 2, "第二场")
            _scene(root, "scene_0001", 1, "第一场")
            _draft(root, "scene_0001", "第一场正文。\n\n## 世界状态变化\n- 不应展示")
            _draft(root, "scene_0002", "第二场正文。")
            (root / "drafts" / "candidates").mkdir(parents=True)
            (root / "drafts" / "candidates" / "scene_0003.md").write_text("候选稿", encoding="utf-8")

            manifest = build_reader_manifest(root)
            self.assertEqual([unit["scene_id"] for unit in manifest["units"]], ["scene_0001", "scene_0002"])
            self.assertNotIn("候选", json.dumps(manifest, ensure_ascii=False))
            unit = read_reader_unit(root, "chapter_0001.scene_0001")
            self.assertEqual(unit["body"], "第一场正文。")
            self.assertNotIn("source_path", public_reader_manifest(manifest)["units"][0])

            cached = build_reader_manifest(root)
            self.assertEqual(cached["project_revision"], manifest["project_revision"])
            _draft(root, "scene_0002", "第二场正文已经更新。")
            updated = build_reader_manifest(root)
            self.assertNotEqual(updated["project_revision"], manifest["project_revision"])

    def test_exported_chapter_with_coverage_replaces_promoted_scenes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_project(root)
            _scene(root, "scene_0001", 1, "第一场")
            _scene(root, "scene_0002", 2, "第二场")
            _draft(root, "scene_0001", "旧正文一。")
            _draft(root, "scene_0002", "旧正文二。")
            export = root / "exports" / "chapter_0001"
            export.mkdir(parents=True)
            (export / "chapter_0001_novel.md").write_text("# 第一章\n\n正式章节正文。", encoding="utf-8")
            (export / "export_manifest.json").write_text(
                json.dumps(
                    {
                        "outputs": {"novel": "exports/chapter_0001/chapter_0001_novel.md"},
                        "exported_scenes": [{"scene_id": "scene_0001"}, {"scene_id": "scene_0002"}],
                    }
                ),
                encoding="utf-8",
            )

            manifest = build_reader_manifest(root)
            self.assertEqual(len(manifest["units"]), 1)
            self.assertEqual(manifest["units"][0]["status"], "exported")
            self.assertEqual(manifest["units"][0]["coverage"], ["scene_0001", "scene_0002"])
            self.assertEqual(search_reader(root, "正式")["items"][0]["unit_id"], "chapter_0001")

    def test_chapter_without_coverage_does_not_hide_promoted_scene(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_project(root)
            _scene(root, "scene_0001", 1, "第一场")
            _draft(root, "scene_0001", "正式场景。")
            chapter = root / "drafts" / "chapters"
            chapter.mkdir(parents=True)
            (chapter / "chapter_0001.md").write_text("无覆盖说明的章节。", encoding="utf-8")

            manifest = build_reader_manifest(root)
            self.assertEqual(manifest["units"][0]["scene_id"], "scene_0001")
            self.assertTrue(any(item["code"] == "coverage_missing" for item in manifest["warnings"]))

    def test_five_hundred_thousand_character_manifest_is_metadata_only_and_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _seed_project(root)
            for index in range(1, 101):
                scene_id = f"scene_{index:04d}"
                chapter_id = f"chapter_{index:04d}"
                folder = root / "scenes"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{scene_id}.yaml").write_text(
                    f"scene_id: {scene_id}\nchapter_id: {chapter_id}\nscene_order: 1\ntitle: 第{index}节\n",
                    encoding="utf-8",
                )
                _draft(root, scene_id, "潮" * 5000)

            started = time.perf_counter()
            manifest = build_reader_manifest(root)
            first_elapsed = time.perf_counter() - started
            started = time.perf_counter()
            cached = build_reader_manifest(root)
            cached_elapsed = time.perf_counter() - started
            public = public_reader_manifest(manifest)

            self.assertEqual(len(public["units"]), 100)
            self.assertGreaterEqual(public["total_chinese_content_chars"], 500000)
            self.assertTrue(all("body" not in unit for unit in public["units"]))
            self.assertTrue(all(unit.get("body_endpoint") for unit in public["units"]))
            self.assertLess(len(json.dumps(public, ensure_ascii=False)), 150000)
            self.assertEqual(cached["project_revision"], manifest["project_revision"])
            self.assertLess(first_elapsed, 5.0)
            self.assertLess(cached_elapsed, first_elapsed)


def _seed_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.yaml").write_text("project:\n  title: Reader Test\n", encoding="utf-8")


def _scene(root: Path, scene_id: str, order: int, title: str) -> None:
    folder = root / "scenes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{scene_id}.yaml").write_text(
        f"scene_id: {scene_id}\nchapter_id: chapter_0001\nscene_order: {order}\ntitle: {title}\n",
        encoding="utf-8",
    )


def _draft(root: Path, scene_id: str, body: str) -> None:
    folder = root / "drafts" / "scenes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{scene_id}.md").write_text(f"## 正文草稿\n\n{body}\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
