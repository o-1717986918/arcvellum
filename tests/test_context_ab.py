from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.context_ab import (
    CONTEXT_AB_SCHEMA,
    _run_arm_with_transient_retry,
    project_content_digest,
    run_context_ab_experiment,
)
from literary_engineering_studio.runtime.worker_results import (
    WorkerRunResult,
)


TASK_ID = "scene-development-scene-0001-candidate-review"
REVIEW_PATH = "reviews/agent/scene_0001_scene_review.json"


class _FakeWorker:
    fail_bounded = False

    def __init__(self, config, *, event_sink):
        self.config = config
        self.event_sink = event_sink

    def run_once(
        self,
        project: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str,
    ) -> WorkerRunResult:
        mode = self.config["worker"]["context_budget"]["mode"]
        runs_root = Path(self.config["worker"]["runs_root"])
        run_root = runs_root / f"fake-{mode}"
        workspace = run_root / "workspace"
        workspace.mkdir(parents=True)
        task = load_task_package(
            project,
            project / "workflow" / "tasks" / f"{task_id}.task.json",
        )
        review = project / REVIEW_PATH
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text(
            json.dumps(
                {
                    "schema": "literary-engineering/scene-review/v1",
                    "conclusion": "pass",
                    "blocking_issues": [],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        visible = 1_000 if mode == "shadow" else 400
        context_report = {
            "mode": mode,
            "requested_mode": mode,
            "contract_status": "bounded-ready",
            "rollout_reason": f"test-{mode}",
            "rollout_policy_digest": mode * 8,
            "first_turn_visible_characters": visible,
            "exact_on_demand_characters": 200,
            "mandatory_characters": 100,
            "digest": f"context-{mode}",
        }
        execution_context = {
            "digest": f"execution-{mode}",
            "tier_counts": {
                "must_inline": 1,
                "exact_on_demand": 1,
            },
        }
        (workspace / "TASK_CONTEXT.json").write_text(
            json.dumps(
                {
                    "execution_context": {
                        "must_inline": ["source.md"],
                        "exact_on_demand": ["reference.md"],
                        "excluded": [],
                    }
                }
            ),
            encoding="utf-8",
        )
        (run_root / "run.json").write_text(
            json.dumps(
                {
                    "context_budget": context_report,
                    "execution_context": execution_context,
                }
            ),
            encoding="utf-8",
        )
        base = {
            "task_id": task.task_id,
            "route": task.route,
        }
        self.event_sink("task.opened", base)
        self.event_sink(
            "sandbox.context_ready",
            {
                **base,
                "context_budget": context_report,
                "context_ledger_digest": f"ledger-{mode}",
            },
        )
        self.event_sink("runner.started", base)
        self.event_sink(
            "usage.updated",
            {
                **base,
                "provider": "test-provider",
                "model": "same-model",
                "usage": {
                    "input": 1_000 if mode == "shadow" else 400,
                    "output": 50,
                },
            },
        )
        failed = mode == "bounded" and self.fail_bounded
        self.event_sink(
            "validation.failed" if failed else "validation.passed",
            {
                **base,
                "kind": "sandbox-preflight",
                "attempt": 0,
            },
        )
        self.event_sink("runner.completed", base)
        return WorkerRunResult(
            status="preflight_failed" if failed else "complete",
            project_root=project,
            route=route,
            task_id=task_id,
            runtime=runtime_id,
            run_root=run_root,
            workspace=workspace,
            message="fake",
        )


class _FailingBoundedWorker(_FakeWorker):
    fail_bounded = True


class _PreviewWorker(_FakeWorker):
    approvals = 0

    def run_once(
        self,
        project: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str,
    ) -> WorkerRunResult:
        result = super().run_once(
            project,
            route=route,
            runtime_id=runtime_id,
            task_id=task_id,
        )
        return WorkerRunResult(
            status="waiting_writeback",
            project_root=result.project_root,
            route=result.route,
            task_id=result.task_id,
            runtime=result.runtime,
            run_root=result.run_root,
            workspace=result.workspace,
            message="preview",
        )

    def approve_writeback(
        self,
        run_root: Path,
        *,
        approved_by: str,
    ) -> WorkerRunResult:
        type(self).approvals += 1
        self.event_sink(
            "writeback.approved",
            {"approved_by": approved_by},
        )
        return WorkerRunResult(
            status="complete",
            project_root=run_root.parent.parent / "project",
            route="scene-development",
            task_id=TASK_ID,
            runtime="fake-runtime",
            run_root=run_root,
            workspace=run_root / "workspace",
            message="approved",
        )


class _BrokenPreviewWorker(_PreviewWorker):
    def approve_writeback(
        self,
        run_root: Path,
        *,
        approved_by: str,
    ) -> WorkerRunResult:
        raise ValueError("preview changed")


class ContextABTests(unittest.TestCase):
    def test_transient_arm_failure_retries_once_in_a_fresh_attempt(self):
        failed = {
            "status": "runtime_failed",
            "failure": {"present": True, "retryable": True},
            "elapsed_seconds": 2.5,
        }
        completed = {
            "status": "complete",
            "failure": {"present": False, "retryable": False},
            "elapsed_seconds": 3.5,
        }
        with patch(
            "literary_engineering_studio.runtime.context_ab._run_arm",
            side_effect=[failed, completed],
        ) as run_arm:
            report = _run_arm_with_transient_retry(
                Path("."),
                "scene-development",
                TASK_ID,
                "opencode",
                {},
                "shadow",
                Path("arm"),
                _FakeWorker,
            )

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["elapsed_seconds"], 6.0)
        self.assertEqual(report["experiment_attempts"], 2)
        self.assertEqual(report["experiment_transient_retries"], 1)
        self.assertEqual(
            [call.args[6] for call in run_arm.call_args_list],
            [Path("arm/attempt-1"), Path("arm/attempt-2")],
        )

    def test_isolated_same_model_experiment_accepts_safe_canary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            _write_project(project)
            before = project_content_digest(project)
            output = root / "context-ab.json"

            with patch(
                "literary_engineering_studio.runtime.context_ab."
                "_refresh_task_contract"
            ) as refresh:
                report = run_context_ab_experiment(
                    project,
                    task_id=TASK_ID,
                    runtime_id="fake-runtime",
                    config={"worker": {"context_budget": {}}},
                    output_path=output,
                    worker_factory=_FakeWorker,
                )

            self.assertEqual(report["schema"], CONTEXT_AB_SCHEMA)
            self.assertEqual(refresh.call_count, 2)
            self.assertTrue(report["canary_candidate"])
            self.assertEqual(
                report["comparison"][
                    "first_turn_visible_character_reduction"
                ],
                0.6,
            )
            self.assertTrue(
                report["criteria"]["requested_modes_applied"]
            )
            self.assertTrue(
                report["criteria"][
                    "bounded_did_not_add_repair_or_retry_turns"
                ]
            )
            self.assertEqual(before, project_content_digest(project))
            self.assertEqual(
                report["original_project_digest_before"],
                report["original_project_digest_after"],
            )
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(str(project), serialized)
            self.assertNotIn("正文不得进入报告", serialized)
            self.assertTrue(output.is_file())

    def test_failed_bounded_arm_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            _write_project(project)

            with patch(
                "literary_engineering_studio.runtime.context_ab."
                "_refresh_task_contract"
            ):
                report = run_context_ab_experiment(
                    project,
                    task_id=TASK_ID,
                    runtime_id="fake-runtime",
                    config={"worker": {"context_budget": {}}},
                    worker_factory=_FailingBoundedWorker,
                )

            self.assertFalse(report["canary_candidate"])
            self.assertFalse(report["criteria"]["both_complete"])
            self.assertFalse(
                report["criteria"]["both_first_preflight_pass"]
            )

    def test_preview_writeback_is_finalized_only_inside_arm_copies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            _write_project(project)
            before = project_content_digest(project)
            _PreviewWorker.approvals = 0

            with patch(
                "literary_engineering_studio.runtime.context_ab."
                "_refresh_task_contract"
            ):
                report = run_context_ab_experiment(
                    project,
                    task_id=TASK_ID,
                    runtime_id="fake-runtime",
                    config={"worker": {"context_budget": {}}},
                    worker_factory=_PreviewWorker,
                )

            self.assertEqual(_PreviewWorker.approvals, 2)
            self.assertTrue(report["criteria"]["both_complete"])
            self.assertTrue(report["canary_candidate"])
            self.assertEqual(before, project_content_digest(project))

    def test_preview_writeback_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _write_project(project)

            with patch(
                "literary_engineering_studio.runtime.context_ab."
                "_refresh_task_contract"
            ), self.assertRaisesRegex(
                RuntimeError,
                "isolated writeback approval failed",
            ):
                run_context_ab_experiment(
                    project,
                    task_id=TASK_ID,
                    runtime_id="fake-runtime",
                    config={"worker": {"context_budget": {}}},
                    worker_factory=_BrokenPreviewWorker,
                )

    def test_report_cannot_be_written_inside_source_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            _write_project(project)

            with self.assertRaisesRegex(
                ValueError,
                "outside the source project",
            ):
                run_context_ab_experiment(
                    project,
                    task_id=TASK_ID,
                    runtime_id="fake-runtime",
                    config={"worker": {"context_budget": {}}},
                    output_path=project / "workflow" / "ab.json",
                    worker_factory=_FakeWorker,
                )


def _write_project(project: Path) -> None:
    task_root = project / "workflow" / "tasks"
    task_root.mkdir(parents=True)
    (project / "source.md").write_text(
        "正文不得进入报告",
        encoding="utf-8",
    )
    (project / "reference.md").write_text(
        "参考资料",
        encoding="utf-8",
    )
    markdown = task_root / f"{TASK_ID}.agent_tasks.md"
    markdown.write_text("# Candidate review\n", encoding="utf-8")
    payload = {
        "schema": "literary-engineering-workbench/agent-task/v1",
        "task_id": TASK_ID,
        "status": "opened",
        "route": "scene-development",
        "current_state": "candidate-review",
        "task_type": "platform-agent-review",
        "required_reading": [],
        "source_paths": ["source.md", "reference.md"],
        "agent_source_paths": ["source.md", "reference.md"],
        "expected_outputs": [REVIEW_PATH],
        "validation_gates": [],
        "forbidden_shortcuts": [],
        "task_markdown": (
            f"workflow/tasks/{TASK_ID}.agent_tasks.md"
        ),
        "context_contract_required": True,
        "context_contract_schema": (
            "literary-engineering-workbench/task-context-contract/v1"
        ),
        "context_contract_revision": "test-v1",
        "context_contract_status": "bounded-ready",
        "context_must_inline_paths": ["source.md"],
        "context_exact_on_demand_paths": ["reference.md"],
        "context_summary_reference_paths": [],
        "context_excluded_paths": [],
    }
    (task_root / f"{TASK_ID}.task.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
