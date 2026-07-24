from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.word_budget import (
    build_word_budget,
    load_word_budget_summary,
    render_scene_word_budget_contract,
    scene_word_budget_contract,
    word_budget_adherence_for_body,
)
from literary_engineering_studio_engine.text_counts import CHINESE_CONTENT_COUNT_UNIT
from unittest.mock import patch


class WordBudgetModuleBoundaryTests(unittest.TestCase):
    def test_build_keeps_budget_inventory_and_task_artifacts_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "project.yaml").write_text(
                "target_length: 120000\nvolumes: 2\ngenre: mystery\n",
                encoding="utf-8",
            )
            (root / "plot" / "outline.md").write_text("# 第一卷\n## 第一章\n", encoding="utf-8")

            result = build_word_budget(root)
            summary = load_word_budget_summary(root)

            self.assertEqual(result.target_words, 120000)
            self.assertTrue(result.json_path.is_file())
            self.assertTrue(result.agent_tasks_path.is_file())
            self.assertEqual(summary["target"]["target_chinese_chars"], 120000)
            self.assertIn("chapter_rows", summary["scene_inventory_binding"])

    def test_scene_contract_preserves_chinese_character_budget_and_renderer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            (root / "project.yaml").write_text("target_length: 120000\n", encoding="utf-8")
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\n", encoding="utf-8")
            budget = {
                "status": "pass",
                "target": {"target_chinese_chars": 120000},
                "totals": {"target_words": 120000},
                "chapter_budgets": [
                    {
                        "chapter_id": "chapter_0001",
                        "target_words": 3600,
                        "scene_count": 3,
                        "avg_scene_words": 1200,
                        "required_functions": ["mainline_action"],
                    }
                ],
                "scene_inventory_binding": {"chapter_rows": []},
            }
            budget_path = root / "plot" / "word_budget" / "word_budget.json"
            budget_path.parent.mkdir(parents=True)
            budget_path.write_text(json.dumps(budget, ensure_ascii=False), encoding="utf-8")

            contract = scene_word_budget_contract(root, scene)

            self.assertEqual(contract["status"], "pass")
            self.assertEqual(contract["target_chinese_chars"], 1200)
            self.assertEqual(contract["count_unit"], CHINESE_CONTENT_COUNT_UNIT)
            self.assertIn("目标中文内容字符：1200", render_scene_word_budget_contract(root, scene))

    def test_scoped_candidate_budget_accepts_registered_active_scene_in_isolated_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scenes" / "scene_0001.yaml"
            scene.parent.mkdir(parents=True)
            (root / "project.yaml").write_text("target_length: 120000\n", encoding="utf-8")
            scene.write_text("scene_id: scene_0001\nchapter_id: chapter_0001\nword_count_target: 4\n", encoding="utf-8")
            budget_path = root / "plot" / "word_budget" / "word_budget.json"
            budget_path.parent.mkdir(parents=True)
            budget_path.write_text(
                json.dumps(
                    {
                        "status": "needs_expansion",
                        "target": {"target_chinese_chars": 120000},
                        "totals": {"target_words": 120000},
                        "chapter_budgets": [{"chapter_id": "chapter_0001", "target_words": 4, "scene_count": 1, "avg_scene_words": 4}],
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "literary_engineering_studio_engine.literary.planning.contracts.longform_materialization_status",
                side_effect=lambda _root, *, scene_path=None: (scene_path is not None, "scoped materialization"),
            ):
                adherence = word_budget_adherence_for_body(root, scene, "甲乙丙丁", materialization_scope="scene")
            self.assertEqual(adherence["status"], "pass")


if __name__ == "__main__":
    unittest.main()
