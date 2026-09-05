from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.longform_planning_route import (
    _repair_targets_changed,
    blueprint_for_state,
    build_task_payload,
)


class LongformRevisionLoopTests(unittest.TestCase):
    def test_budget_review_and_revision_are_separate_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\ntarget_length: 100000\n", encoding="utf-8")
            candidate = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("# 预算大纲\n\n库存不足。\n", encoding="utf-8")
            state = {"current_step": "budget-review", "target_id": "longform", "scene_id": "longform"}

            payload = build_task_payload(root, "longform-planning", state)

            self.assertEqual(payload["task_type"], "platform-agent-review")
            self.assertNotIn(candidate.relative_to(root).as_posix(), payload["expected_outputs"])
            self.assertIn("reviews/word_budget/word_budget_review.json", payload["expected_outputs"])

            revision = build_task_payload(
                root,
                "longform-planning",
                {"current_step": "budget-revision", "target_id": "longform", "scene_id": "longform"},
            )
            self.assertEqual(revision["task_type"], "platform-agent-revision")
            self.assertIn(candidate.relative_to(root).as_posix(), revision["expected_outputs"])
            self.assertTrue(_repair_targets_changed(root, revision, "budget revision"))
            candidate.write_text("# 预算大纲\n\n补入新的因果事件、关系压力与兑现节点。\n", encoding="utf-8")
            self.assertEqual(_repair_targets_changed(root, revision, "budget revision"), [])

    def test_chapter_obligation_route_has_a_reviewable_plan_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            blueprint = blueprint_for_state(root, "chapter-obligation-agent-task", "")
            self.assertIn("plot/candidates/chapters/chapter_obligation_plan.md", blueprint["expected_outputs"])
            review = blueprint_for_state(root, "chapter-obligation-review", "")
            self.assertNotIn("repair_targets", review)
            self.assertIn("reviews/word_budget/chapter_obligation_review.json", review["expected_outputs"])
            revision = blueprint_for_state(root, "chapter-obligation-revision", "")
            self.assertIn("plot/candidates/chapters/chapter_obligation_plan.md", revision["repair_targets"])


if __name__ == "__main__":
    unittest.main()
