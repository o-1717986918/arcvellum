from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.projections.reader import _chapter_ids as reader_chapter_ids
from literary_engineering_studio_engine.literary.planning.chapter_inventory import (
    formal_chapter_files,
    formal_chapter_ids,
    formal_scene_ids_for_chapter,
    is_final_chapter,
)
from literary_engineering_studio_engine.literary.review.longform_audit import _chapter_files
from literary_engineering_studio_engine.workflow.state_export_release import _export_release_states


class ChapterInventoryContractTests(unittest.TestCase):
    def test_scene_assets_exclude_aggregate_and_derivative_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  title: Inventory\n")
            self._scene(root, "scene_0001", "chapter_0001")
            self._scene(root, "scene_0002", "chapter_0002")
            self._chapter(root, "chapter_0001", ["chapter_0001"])
            self._chapter(root, "chapter_0002", ["chapter_0002"])
            self._chapter(root, "chapter_001", ["chapter_0001", "chapter_0002"])
            for relative in (
                "exports/chapter_001/export_manifest.json",
                "releases/chapter_001/latest.json",
                "drafts/chapters/chapter_001.md",
            ):
                self._write(root / relative, "{}\n")

            self.assertEqual(formal_chapter_ids(root), ("chapter_0001", "chapter_0002"))
            self.assertEqual(
                formal_scene_ids_for_chapter(root, "chapter_0001"),
                ("scene_0001",),
            )
            self.assertEqual(
                formal_scene_ids_for_chapter(root, "chapter_0002"),
                ("scene_0002",),
            )
            self.assertEqual(
                tuple(path.stem for path in formal_chapter_files(root)),
                ("chapter_0001", "chapter_0002"),
            )
            self.assertEqual(
                [item["chapter_id"] for item in _export_release_states(root)],
                ["chapter_0001", "chapter_0002"],
            )
            self.assertEqual(
                [path.stem for path in _chapter_files(root)],
                ["chapter_0001", "chapter_0002"],
            )
            self.assertEqual(
                reader_chapter_ids(
                    root,
                    [
                        {"chapter_id": "chapter_0001"},
                        {"chapter_id": "chapter_0002"},
                    ],
                ),
                ["chapter_0001", "chapter_0002"],
            )
            self.assertFalse(is_final_chapter(root, "chapter_0001"))
            self.assertTrue(is_final_chapter(root, "chapter_0002"))

    def test_planning_project_falls_back_to_word_budget_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root / "project.yaml", "project:\n  title: Planned\n")
            self._write(
                root / "plot/word_budget/word_budget.json",
                json.dumps(
                    {
                        "chapter_budgets": [
                            {"chapter_id": "chapter_0001"},
                            {"chapter_id": "chapter_0002"},
                        ]
                    }
                ),
            )
            self._chapter(root, "chapter_001", ["chapter_0001", "chapter_0002"])

            self.assertEqual(formal_chapter_ids(root), ("chapter_0001", "chapter_0002"))

    @classmethod
    def _scene(cls, root: Path, scene_id: str, chapter_id: str) -> None:
        cls._write(
            root / "scenes" / f"{scene_id}.yaml",
            f"scene_id: {scene_id}\nchapter_id: {chapter_id}\n",
        )

    @classmethod
    def _chapter(cls, root: Path, chapter_id: str, scene_chapters: list[str]) -> None:
        cls._write(
            root / "plot" / "chapters" / f"{chapter_id}.json",
            json.dumps(
                {
                    "chapter_id": chapter_id,
                    "summary": {"ready_count": len(scene_chapters), "blocked_count": 0},
                    "scenes": [
                        {"scene_id": f"scene_{index:04d}", "chapter_id": value, "status": "ready"}
                        for index, value in enumerate(scene_chapters, start=1)
                    ],
                }
            ),
        )

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
