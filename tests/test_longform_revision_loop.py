from pathlib import Path
import tempfile
import unittest

import literary_engineering_studio_engine.task_registry as task_registry


class LongformRevisionLoopTests(unittest.TestCase):
    def test_budget_review_task_can_revise_candidate_and_requires_real_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\ntarget_length: 100000\n", encoding="utf-8")
            candidate = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
            candidate.parent.mkdir(parents=True)
            candidate.write_text("# 预算大纲\n\n库存不足。\n", encoding="utf-8")
            review = root / "reviews" / "word_budget" / "word_budget_review.md"
            review.parent.mkdir(parents=True)
            review.write_text("- 结论： revise_required\n", encoding="utf-8")
            state = {"current_step": "budget-review", "target_id": "longform", "scene_id": "longform"}

            payload = task_registry._build_longform_task_payload(root, "longform-planning", state)

            self.assertEqual(payload["task_type"], "platform-agent-revision")
            self.assertIn(candidate.relative_to(root).as_posix(), payload["expected_outputs"])
            self.assertTrue(task_registry._declared_repair_targets_changed(root, payload, "budget revision"))
            candidate.write_text("# 预算大纲\n\n补入新的因果事件、关系压力与兑现节点。\n", encoding="utf-8")
            self.assertEqual(task_registry._declared_repair_targets_changed(root, payload, "budget revision"), [])

    def test_chapter_obligation_route_has_a_reviewable_plan_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project.yaml").write_text("title: 潮线\n", encoding="utf-8")
            blueprint = task_registry._longform_blueprint_for_state(root, "chapter-obligation-agent-task", "")
            self.assertIn("plot/candidates/chapters/chapter_obligation_plan.md", blueprint["expected_outputs"])
            review = task_registry._longform_blueprint_for_state(root, "chapter-obligation-review", "")
            self.assertIn("plot/candidates/chapters/chapter_obligation_plan.md", review["repair_targets"])


if __name__ == "__main__":
    unittest.main()
