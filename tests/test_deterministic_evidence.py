import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.deterministic_evidence import (
    project_target_length,
    refresh_deterministic_evidence,
)
from literary_engineering_studio.runtime.worker_writeback import WritebackCoordinator


class _Result:
    def require_success(self):
        return self


class _Bridge:
    def __init__(self, *, completion_error=None):
        self.calls = []
        self.completion_error = completion_error

    def run(self, args, *, timeout=180):
        self.calls.append((list(args), timeout))
        return _Result()

    def task_submit(self, *_args, **_kwargs):
        self.calls.append(("task-submit", 0))

    def task_complete(self, *_args, **_kwargs):
        self.calls.append(("task-complete", 0))
        if self.completion_error:
            raise self.completion_error

    def task_revert_submission(self, *_args, **_kwargs):
        self.calls.append(("task-revert-submission", 0))


def _task(root: Path, state: str) -> TaskPackage:
    return TaskPackage(
        project_root=root,
        task_json_path=root / "task.json",
        task_markdown_path=root / "task.md",
        payload={
            "task_id": "project-review",
            "route": "review-and-audit",
            "current_state": state,
            "task_type": "platform-agent-revision",
            "expected_outputs": [],
        },
    )


class DeterministicEvidenceTests(unittest.TestCase):
    def test_canon_revision_refreshes_only_canon_lint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge = _Bridge()

            paths = refresh_deterministic_evidence(
                bridge, _task(root, "canon-review-pass"), root
            )

            self.assertEqual(len(bridge.calls), 1)
            self.assertEqual(bridge.calls[0][0][0], "canon-lint")
            self.assertEqual(
                paths,
                ("reviews/canon_lint.md", "reviews/canon_lint.json"),
            )

    def test_committee_revision_uses_formal_budget_for_both_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            budget = root / "plot" / "word_budget" / "word_budget.json"
            budget.parent.mkdir(parents=True)
            budget.write_text(
                json.dumps({"target": {"target_chinese_chars": 30000}}),
                encoding="utf-8",
            )
            bridge = _Bridge()

            paths = refresh_deterministic_evidence(
                bridge, _task(root, "committee-pass"), root
            )

            self.assertEqual(project_target_length(root), 30000)
            self.assertEqual([call[0][0] for call in bridge.calls], ["canon-lint", "longform-audit"])
            self.assertIn("30000", bridge.calls[1][0])
            self.assertEqual(len(paths), 5)

    def test_unrelated_task_does_not_refresh_project_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge = _Bridge()

            paths = refresh_deterministic_evidence(
                bridge, _task(root, "candidate-review"), root
            )

            self.assertEqual(paths, ())
            self.assertEqual(bridge.calls, [])

    def test_writeback_refreshes_evidence_before_core_submission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge = _Bridge()
            coordinator = WritebackCoordinator(bridge, SimpleNamespace(emit=lambda *_: None))
            task = _task(root, "canon-review-pass")
            sandbox = SimpleNamespace(
                manifest_path=root / "run.json",
                run_root=root,
                workspace=root / "workspace",
            )
            mutations = SimpleNamespace(
                applied=lambda *_: None,
                promoted=lambda *_: None,
                rolled_back=lambda *_: None,
            )
            with (
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.apply_expected_outputs",
                    return_value=("scenes/scene_0001.yaml",),
                ),
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.load_run",
                    return_value={"runtime": "pi-worker"},
                ),
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.update_run_manifest"
                ),
                patch.object(coordinator, "_mutation_tracker", return_value=mutations),
            ):
                result = coordinator._finalize(
                    task,
                    sandbox,
                    SimpleNamespace(as_dict=lambda: {}),
                    approved_by="policy:automatic",
                )

            self.assertEqual(result.status, "complete")
            self.assertEqual(bridge.calls[0][0][0], "canon-lint")
            self.assertEqual(bridge.calls[1][0], "task-submit")
            self.assertEqual(bridge.calls[2][0], "task-complete")

    def test_failed_gate_rolls_back_sources_before_evidence_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = []
            bridge = _Bridge(completion_error=ValueError("forced gate failure"))
            coordinator = WritebackCoordinator(bridge, SimpleNamespace(emit=lambda *_: None))
            task = _task(root, "canon-review-pass")
            sandbox = SimpleNamespace(
                manifest_path=root / "run.json",
                run_root=root,
                workspace=root / "workspace",
            )
            mutations = SimpleNamespace(
                applied=lambda *_: None,
                promoted=lambda *_: None,
                rolled_back=lambda *_: None,
            )

            def rollback(*_args):
                events.append("sources-rolled-back")

            def tracked_run(args, *, timeout=180):
                events.append(args[0])
                return _Result()

            bridge.run = tracked_run
            with (
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.apply_expected_outputs",
                    return_value=("scenes/scene_0001.yaml",),
                ),
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.rollback_expected_outputs",
                    side_effect=rollback,
                ),
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.load_run",
                    return_value={"runtime": "pi-worker"},
                ),
                patch(
                    "literary_engineering_studio.runtime.worker_writeback.update_run_manifest"
                ),
                patch.object(coordinator, "_mutation_tracker", return_value=mutations),
            ):
                result = coordinator._finalize(
                    task,
                    sandbox,
                    SimpleNamespace(as_dict=lambda: {}),
                    approved_by="policy:automatic",
                )

            self.assertEqual(result.status, "blocked_by_core_gate")
            self.assertEqual(
                events,
                ["canon-lint", "sources-rolled-back", "canon-lint"],
            )


if __name__ == "__main__":
    unittest.main()
