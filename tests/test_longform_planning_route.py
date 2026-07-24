from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.longform_planning_route import build_task_payload, validate_task


class LongformPlanningRouteTests(unittest.TestCase):
    def test_word_budget_task_preserves_story_architecture_first_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "scenes").mkdir()
            (root / "project.yaml").write_text(
                "target_length: 500000\nvolumes: 5\ngenre: historical-fantasy\n",
                encoding="utf-8",
            )
            (root / "plot" / "outline.md").write_text("# outline\n", encoding="utf-8")

            payload = build_task_payload(
                root,
                "longform-planning",
                {"current_step": "word-budget-file"},
            )

            self.assertEqual(payload["task_type"], "deterministic-cli")
            self.assertEqual(
                payload["command"],
                "python -m literary_engineering_studio_engine word-budget <project> --target-words 500000 --volumes 5 --genre historical-fantasy",
            )
            self.assertEqual(payload["word_count_target"], 500000)
            self.assertIn("plot/word_budget/word_budget.agent_tasks.md", payload["expected_outputs"])
            self.assertIn("plot/chapter_obligations/chapter_obligations.agent_tasks.md", payload["expected_outputs"])
            self.assertIn("Do not start bulk scene generation while longform-planning is blocked.", payload["forbidden_shortcuts"])

    def test_budget_stage_cannot_bypass_reviewed_story_architecture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "project.yaml").write_text("target_length: 100000\n", encoding="utf-8")

            errors, notes = validate_task(root, {"current_state": "budget-agent-task"})

            self.assertEqual(notes, [])
            self.assertTrue(any(error.startswith("story architecture gate:") for error in errors))


if __name__ == "__main__":
    unittest.main()
