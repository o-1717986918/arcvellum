from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.common import PreflightIssue, PreflightResult
from literary_engineering_studio.runtime.progress_policy import build_runtime_progress_digest
from literary_engineering_studio.runtime.sandbox import SandboxManifest
from literary_engineering_studio.runtime.task_completion import build_task_completion_contract
from literary_engineering_studio.runtime.task_program import build_task_context, render_worker_program


class TaskCompletionContractTests(unittest.TestCase):
    def test_v2_context_projects_agent_outputs_profile_and_pass_condition(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary))
            profile = {"schema": "arcvellum/task-execution-profile/v1", "mode": "shadow", "digest": "a" * 64}

            context = build_task_context(task, execution_profile=profile)

            self.assertEqual(context["schema"], "literary-engineering-studio/task-context/v0.2")
            self.assertIn("literary-engineering-studio/task-context/v0.1", context["compatible_with"])
            self.assertEqual(context["execution_profile"], profile)
            completion = context["completion_contract"]
            self.assertEqual(
                [item["path"] for item in completion["agent_owned_outputs"]],
                ["reviews/word_budget/word_budget_review.md"],
            )
            self.assertEqual(
                completion["studio_managed_completion_evidence"],
                ["plot/word_budget/word_budget.agent_completion.json"],
            )
            self.assertIn(
                "review_machine_conclusion_is_pass",
                completion["semantic_pass_condition"]["required_checks"],
            )

    def test_worker_program_front_loads_read_output_pass_and_stop_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary))

            program = render_worker_program(task)

            headings = [
                "## 必须读取",
                "## Allowed Outputs",
                "## Semantic Evidence",
                "## 精确通过条件",
                "## 停止条件",
                "## Execution Context",
            ]
            positions = [program.index(item) for item in headings]
            self.assertEqual(positions, sorted(positions))
            self.assertIn("review_machine_conclusion_is_pass", program)
            self.assertIn("聊天内容不计入产物", program)

    def test_recorded_review_contract_renders_exact_machine_line_examples(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary), gate="word-budget review conclusion is recorded")

            program = render_worker_program(task)

            self.assertIn("`- 结论： pass`", program)
            self.assertIn("`- 结论： revise_required`", program)
            self.assertIn("标题、代码字段或普通段落不能替代", program)

    def test_progress_digest_changes_only_with_machine_visible_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root)
            sandbox = _sandbox(root)
            output = sandbox.workspace / "reviews/word_budget/word_budget_review.md"
            output.parent.mkdir(parents=True)
            output.write_text("- 结论： revise_required\n", encoding="utf-8")
            result = PreflightResult(
                False,
                (PreflightIssue("review-not-pass", str(output), "bad", "repair"),),
            )

            first = build_runtime_progress_digest(task, sandbox, result, context_access={"read_tool_calls": 1})
            second = build_runtime_progress_digest(task, sandbox, result, context_access={"read_tool_calls": 1})
            output.write_text("- 结论： pass\n", encoding="utf-8")
            changed = build_runtime_progress_digest(task, sandbox, result, context_access={"read_tool_calls": 1})

            self.assertEqual(first.digest, second.digest)
            self.assertNotEqual(first.digest, changed.digest)


def _task(root: Path, *, gate: str = "word-budget review conclusion is pass") -> TaskPackage:
    review = "reviews/word_budget/word_budget_review.md"
    sidecar = "plot/word_budget/word_budget.agent_tasks.md"
    receipt = "plot/word_budget/word_budget.agent_completion.json"
    return TaskPackage(
        root,
        root / "task.json",
        root / "task.md",
        {
            "task_id": "longform-budget-review",
            "route": "longform-planning",
            "current_state": "budget-review",
            "task_type": "platform-agent-revision",
            "execution_policy": "agent-required",
            "agent_role": "independent-review-agent",
            "human_gate": {"required": False, "reasons": [], "source": "test"},
            "runtime_capabilities_required": ["filesystem-read", "filesystem-write"],
            "source_paths": [sidecar],
            "agent_source_paths": [sidecar],
            "expected_outputs": [review, sidecar, receipt],
            "core_managed_outputs": [sidecar],
            "output_contracts": [
                {"path": review, "kind": "semantic-review", "writeback_policy": "automatic"},
                {"path": sidecar, "kind": "task-scaffold", "writeback_policy": "automatic"},
                {"path": receipt, "kind": "completion-evidence", "writeback_policy": "automatic"},
            ],
            "validation_gates": [gate],
        },
    )


def _sandbox(root: Path) -> SandboxManifest:
    run_root = root / "run"
    workspace = run_root / "workspace"
    workspace.mkdir(parents=True)
    return SandboxManifest(
        run_id="run-1",
        run_root=run_root,
        workspace=workspace,
        prompt_path=workspace / "AGENT_TASK.md",
        manifest_path=run_root / "run.json",
        baseline_path=run_root / "agent-baseline.json",
        expected_outputs=(),
        control_workspace=run_root / "control-workspace",
        agent_workspace=workspace,
    )


if __name__ == "__main__":
    unittest.main()
