import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from literary_engineering_studio.projections.partial_delivery import create_partial_docx


class PartialDeliveryTests(unittest.TestCase):
    def test_unfinished_work_exports_only_committed_scenes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 尚未写完\n", encoding="utf-8")
            scenes = root / "scenes"
            scenes.mkdir()
            for number in (1, 2):
                (scenes / f"scene_{number:04d}.yaml").write_text(
                    f"scene_id: scene_{number:04d}\nchapter_id: chapter_0001\n", encoding="utf-8",
                )
            prose = root / "drafts" / "scenes" / "scene_0001.md"
            prose.parent.mkdir(parents=True)
            prose.write_text("窗前有人停下。\n", encoding="utf-8")
            receipt = root / "workflow" / "scene_commits" / "scene_0001.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"prose_sha256": hashlib.sha256("窗前有人停下。".encode()).hexdigest()}), encoding="utf-8")
            (prose.parent / "scene_0002.md").write_text("未审的候选稿。\n", encoding="utf-8")

            result = create_partial_docx(root)

            self.assertEqual(result["status"], "partial_snapshot")
            self.assertEqual(result["manifest"]["source_prose"], ["drafts/scenes/scene_0001.md"])
            with ZipFile(root / result["docx_path"]) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("窗前有人停下", xml)
            self.assertNotIn("未审的候选稿", xml)

    def test_changed_formal_prose_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: test\n", encoding="utf-8")
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8",
            )
            prose = root / "drafts" / "scenes" / "scene_0001.md"
            prose.parent.mkdir(parents=True)
            prose.write_text("已被改动。\n", encoding="utf-8")
            receipt = root / "workflow" / "scene_commits" / "scene_0001.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"prose_sha256": "old"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "回执不一致"):
                create_partial_docx(root)


if __name__ == "__main__":
    unittest.main()
