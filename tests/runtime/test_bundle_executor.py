from __future__ import annotations

from pathlib import Path
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.orchestration.bundles import ExecutionBundle
from literary_engineering_studio.runtime.bundle_executor import SerialBundleExecutor
from literary_engineering_studio.runtime.worker_results import WorkerRunResult


def _bundle() -> ExecutionBundle:
    return ExecutionBundle(
        bundle_id="scene-analysis-scene_0001-test",
        plan_id="plan-test",
        template_id="scene-analysis",
        scope_kind="scene",
        scope_key="scene_0001",
        step_node_ids=("roleplay", "branches"),
        agent_role="main-review-agent",
        expected_outputs=("branches/scene_0001/roleplay.md",),
        base_revision="revision-one",
        context_snapshot_hash="context-one",
        atomic_writeback_group="scene-analysis:scene_0001",
        stop_before=("branch_selection",),
    )


def _task(task_id: str, node_id: str, node_kind: str, *, role: str = "main-review-agent") -> TaskPackage:
    return TaskPackage(
        project_root=Path("C:/work"),
        task_json_path=Path("C:/work/workflow/tasks") / f"{task_id}.task.json",
        task_markdown_path=Path("C:/work/workflow/tasks") / f"{task_id}.md",
        payload={
            "task_id": task_id,
            "route": "scene-development",
            "scene_id": "scene_0001",
            "creative_plan_id": "plan-test",
            "creative_plan_node_id": node_id,
            "creative_plan_node_kind": node_kind,
            "creative_plan_agent_role": role,
        },
    )


def _result(task: TaskPackage, status: str = "complete") -> WorkerRunResult:
    return WorkerRunResult(
        status,
        task.project_root,
        task.route,
        task.task_id,
        "opencode",
        None,
        None,
        status,
    )


class SerialBundleExecutorTests(unittest.TestCase):
    def test_executes_formal_tasks_and_stops_before_declared_boundary(self):
        tasks = iter(
            (
                _task("rp-prepare", "roleplay", "roleplay_simulation"),
                _task("rp-fill", "roleplay", "roleplay_simulation"),
                _task("choose", "selection", "branch_selection"),
            )
        )
        executed: list[str] = []
        outcome = SerialBundleExecutor().execute(
            _bundle(),
            next_task=lambda: next(tasks),
            run_task=lambda task: executed.append(task.task_id) or _result(task),
        )

        self.assertEqual(outcome.status, "stopped_before")
        self.assertEqual(executed, ["rp-prepare", "rp-fill"])
        self.assertEqual(outcome.completed_task_ids, tuple(executed))

    def test_role_mismatch_fails_closed_before_execution(self):
        task = _task(
            "writer-task",
            "roleplay",
            "roleplay_simulation",
            role="main-creative-agent",
        )
        executed: list[str] = []
        outcome = SerialBundleExecutor().execute(
            _bundle(),
            next_task=lambda: task,
            run_task=lambda value: executed.append(value.task_id) or _result(value),
        )

        self.assertEqual(outcome.status, "fixed_fallback")
        self.assertIn("role", outcome.reason)
        self.assertEqual(executed, [])

    def test_repeated_formal_task_is_no_progress_not_an_infinite_loop(self):
        task = _task("same-task", "roleplay", "roleplay_simulation")
        calls = 0

        def run(value):
            nonlocal calls
            calls += 1
            return _result(value)

        outcome = SerialBundleExecutor().execute(
            _bundle(),
            next_task=lambda: task,
            run_task=run,
        )

        self.assertEqual(outcome.status, "no_progress")
        self.assertEqual(calls, 1)

    def test_non_complete_worker_result_ends_bundle_immediately(self):
        first = _task("rp-fill", "roleplay", "roleplay_simulation")
        calls = 0

        def next_task():
            nonlocal calls
            calls += 1
            return first

        outcome = SerialBundleExecutor().execute(
            _bundle(),
            next_task=next_task,
            run_task=lambda task: _result(task, "waiting_writeback"),
        )

        self.assertEqual(outcome.status, "task_terminal")
        self.assertEqual(calls, 1)
        self.assertEqual(outcome.final_result.status, "waiting_writeback")


if __name__ == "__main__":
    unittest.main()
