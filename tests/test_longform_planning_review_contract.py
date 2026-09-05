from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.literary.planning.review import (
    planning_review_evidence_paths,
    planning_review_pass_status,
    planning_review_prepare_status,
    planning_revision_review_status,
    planning_review_status,
    prepare_longform_review,
    review_spec,
)


class LongformPlanningReviewContractTests(unittest.TestCase):
    def test_independent_digest_bound_review_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary), "budget")
            result = prepare_longform_review(root, "budget")
            self._complete_review(root, "budget", reviewer="independent-reviewer")

            complete, message, verdict = planning_review_status(root, "budget")
            self.assertTrue(complete, message)
            self.assertEqual(verdict, "pass")
            passed, message = planning_review_pass_status(root, "budget")
            self.assertTrue(passed, message)
            self.assertEqual(result.candidate_sha256, self._sha(result.candidate_path))

    def test_same_writer_and_reviewer_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary), "scene_inventory")
            result = prepare_longform_review(root, "scene_inventory")
            self._complete_review(root, "scene_inventory", reviewer=result.writer_session_id)

            complete, message, _verdict = planning_review_status(root, "scene_inventory")
            self.assertFalse(complete)
            self.assertIn("independent", message)

    def test_candidate_change_invalidates_prepared_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary), "chapter_obligation")
            prepare_longform_review(root, "chapter_obligation")
            self._complete_review(root, "chapter_obligation", reviewer="independent-reviewer")
            candidate = root / review_spec("chapter_obligation").candidate
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\nnew chapter debt\n", encoding="utf-8")

            prepared, message = planning_review_prepare_status(root, "chapter_obligation")
            self.assertFalse(prepared)
            self.assertIn("exact current candidate", message)

    def test_revision_uses_locked_pre_revision_digest_then_requires_fresh_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary), "budget")
            prepared = prepare_longform_review(root, "budget")
            self._complete_review(
                root,
                "budget",
                reviewer="independent-reviewer",
                verdict="revise",
            )
            candidate = prepared.candidate_path
            candidate.write_text(
                candidate.read_text(encoding="utf-8") + "\nAdded causal inventory.\n",
                encoding="utf-8",
            )

            authorized, message = planning_revision_review_status(
                root, "budget", prepared.candidate_sha256
            )
            self.assertTrue(authorized, message)
            current, _message, _verdict = planning_review_status(root, "budget")
            self.assertFalse(current)

    def test_markdown_pass_cannot_replace_structured_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._project(Path(temporary), "budget")
            result = prepare_longform_review(root, "budget")
            result.report_path.write_text("- 结论： pass\n", encoding="utf-8")
            write_agent_completion_marker(result.task_path, root=root, handled_by="reviewer")

            complete, message, _verdict = planning_review_status(root, "budget")
            self.assertFalse(complete)
            self.assertIn("status must be complete", message)

    def test_review_evidence_preserves_formal_writer_identity_in_sandbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / "project"
            project.mkdir()
            root = self._project(project, "budget")
            writer_task = root / "workflow/tasks/budget-writer.task.json"
            writer_task.parent.mkdir(parents=True, exist_ok=True)
            writer_task.write_text(
                json.dumps(
                    {
                        "task_id": "budget-writer",
                        "status": "complete",
                        "current_state": "budget-agent-task",
                        "completed_at": "2026-09-01T00:00:00+00:00",
                        "expected_outputs": [review_spec("budget").candidate],
                    }
                ),
                encoding="utf-8",
            )
            prepared = prepare_longform_review(root, "budget")
            self.assertEqual(prepared.writer_session_id, "studio:writer:budget-writer")
            self._complete_review(root, "budget", reviewer="independent-reviewer")

            evidence = planning_review_evidence_paths(root, "budget")
            self.assertIn("workflow/tasks/budget-writer.task.json", evidence)
            sandbox = base / "sandbox"
            for relative in evidence:
                source = root / relative
                target = sandbox / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            passed, message = planning_review_pass_status(sandbox, "budget")
            self.assertTrue(passed, message)

    @staticmethod
    def _project(root: Path, kind: str) -> Path:
        spec = review_spec(kind)
        (root / "project.yaml").write_text("title: 潮线\ntarget_length: 100000\n", encoding="utf-8")
        budget = root / "plot" / "word_budget" / "word_budget.json"
        budget.parent.mkdir(parents=True, exist_ok=True)
        budget.write_text(json.dumps({"schema": "literary-engineering-workbench/word-budget/v1"}), encoding="utf-8")
        candidate = root / spec.candidate
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text("# candidate\n\nA sufficiently concrete causal plan.\n", encoding="utf-8")
        sidecar = root / spec.author_task
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text("# author task\n", encoding="utf-8")
        write_agent_completion_marker(sidecar, root=root, handled_by="writer")
        return root

    @staticmethod
    def _complete_review(
        root: Path, kind: str, *, reviewer: str, verdict: str = "pass"
    ) -> None:
        spec = review_spec(kind)
        path = root / spec.review
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "complete",
                "reviewer_session_id": reviewer,
                "verdict": verdict,
                "summary": "The candidate satisfies every declared planning dimension.",
                "findings": ["Exact candidate and budget were independently checked."],
                "required_changes": (
                    [] if verdict == "pass" else ["Add concrete causal inventory."]
                ),
            }
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / spec.report).write_text("# Independent review\n\nPass.\n", encoding="utf-8")
        write_agent_completion_marker(root / spec.review_task, root=root, handled_by=reviewer)

    @staticmethod
    def _sha(path: Path) -> str:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
