from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtimes.scene_source_evidence import scene_source_evidence
from tests.test_lean_kernel_v2_pi_runtime import _brief


class SceneAuthorContextTests(unittest.TestCase):
    def test_global_intent_and_chapter_turn_precede_local_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plot").mkdir()
            (root / "scenes").mkdir()
            (root / "plot" / "word_budget").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("本场必须处理旧信。", encoding="utf-8")
            (root / "plot" / "rhythm_plan.json").write_text("RAW_RHYTHM_DUPLICATE", encoding="utf-8")
            (root / "plot" / "word_budget" / "word_budget.json").write_text("RAW_BUDGET_DUPLICATE", encoding="utf-8")
            plan = {
                "premise": "旧承诺改变两个人的命运", "central_question": "林昭会付出什么代价？",
                "ending_choice": "履约并失去家", "scenes": [{"scene_id": "scene_0001", "chapter_id": "chapter_0001"}],
                "chapters": [{"chapter_id": "chapter_0001", "title": "欠债", "dramatic_turn": "秘密被发现",
                              "obligation": "建立债务", "reader_question": "谁留下了承诺？"}],
            }
            (root / "plot" / "lean_project_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            brief = replace(_brief(), source_refs=("scenes/scene_0001.yaml", "plot/rhythm_plan.json",
                                                     "plot/word_budget/word_budget.json"))
            evidence = scene_source_evidence(root, brief, purpose="create", indexed_style=False)
            self.assertLess(evidence.index("旧承诺改变两个人的命运"), evidence.index("本场必须处理旧信"))
            self.assertIn("秘密被发现", evidence)
            self.assertNotIn("RAW_RHYTHM_DUPLICATE", evidence)
            self.assertNotIn("RAW_BUDGET_DUPLICATE", evidence)
            bounded = scene_source_evidence(root, brief, purpose="review", indexed_style=False, max_chars=300)
            self.assertLessEqual(len(bounded), 300)
            self.assertNotIn("RAW_RHYTHM_DUPLICATE", bounded)
            with_plan = scene_source_evidence(root, brief, purpose="review", indexed_style=False, max_chars=1000)
            self.assertIn("全篇创作意图", with_plan)

    def test_without_plan_retains_local_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text("本场旧信。", encoding="utf-8")
            brief = replace(_brief(), source_refs=("scenes/scene_0001.yaml",))
            evidence = scene_source_evidence(root, brief, purpose="create", indexed_style=False)
            self.assertIn("本场旧信", evidence)
            self.assertNotIn("全篇创作意图", evidence)


if __name__ == "__main__":
    unittest.main()
