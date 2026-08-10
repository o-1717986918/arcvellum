from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.preflight.common import (
    PreflightIssue,
    PreflightResult,
)
from literary_engineering_studio.runtime.repair_context import (
    REPAIR_CONTEXT_SCHEMA,
    RepairContextCoordinator,
)
from literary_engineering_studio.runtime.repair_rendering import (
    MAX_EXCERPT_CHARACTERS,
    MAX_TOTAL_EXCERPT_CHARACTERS,
)
from literary_engineering_studio.runtime.context_budget import ContextTaskKind
from literary_engineering_studio.runtime.reasoning_policy import resolve_reasoning_budget
from literary_engineering_studio.runtime.sandbox import SandboxManifest


def _task(root: Path, outputs: tuple[str, ...]) -> TaskPackage:
    core = "out/core.agent_tasks.md"
    completion = "out/result.agent_completion.json"
    all_outputs = (*outputs, core, completion)
    contracts = [
        {
            "path": path,
            "kind": (
                "completion-evidence"
                if path == completion
                else "task-scaffold"
                if path == core
                else "semantic-candidate"
            ),
            "writeback_policy": "automatic",
        }
        for path in all_outputs
    ]
    return TaskPackage(
        root,
        root / "task.json",
        root / "task.md",
        {
            "task_id": "scene-development-scene-0001-review",
            "route": "scene-development",
            "current_state": "candidate-review",
            "task_type": "platform-agent",
            "execution_policy": "agent-required",
            "agent_role": "independent-review-agent",
            "runtime_capabilities_required": [
                "filesystem-read",
                "filesystem-write",
            ],
            "human_gate": {
                "required": False,
                "reasons": [],
                "source": "test",
            },
            "expected_outputs": list(all_outputs),
            "core_managed_outputs": [core],
            "output_contracts": contracts,
        },
    )


def _sandbox(root: Path) -> SandboxManifest:
    workspace = root / "workspace"
    run_root = root / "run"
    workspace.mkdir()
    run_root.mkdir()
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


class IncrementalRepairContextTests(unittest.TestCase):
    def test_targeted_context_is_bounded_and_restores_passed_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(
                root,
                ("out/invalid.json", "out/passed.md"),
            )
            sandbox = _sandbox(root)
            invalid = sandbox.workspace / "out" / "invalid.json"
            passed = sandbox.workspace / "out" / "passed.md"
            invalid.parent.mkdir(parents=True)
            invalid.write_text(
                json.dumps(
                    {"status": "bad", "body": "X" * 5_000},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            passed.write_text(
                "这段已经通过的正文不应进入 repair prompt。",
                encoding="utf-8",
            )
            result = PreflightResult(
                False,
                (
                    PreflightIssue(
                        "review-invalid",
                        "out/invalid.json#status",
                        "status 必须为 pass。",
                        "只把 status 改为 pass。",
                    ),
                ),
            )
            coordinator = RepairContextCoordinator(task, sandbox)

            prepared = coordinator.prepare(result, 1, 2)
            payload = json.loads(
                prepared.artifact_path.read_text(encoding="utf-8")
            )

            self.assertEqual(payload["schema"], REPAIR_CONTEXT_SCHEMA)
            self.assertEqual(payload["write_scope_mode"], "targeted")
            self.assertEqual(
                payload["repair_targets"],
                ["out/invalid.json"],
            )
            self.assertEqual(
                payload["invalid_outputs"][0]["excerpt"].strip(),
                '{\n  "status": "bad"\n}',
            )
            self.assertNotIn("X" * 20, prepared.prompt)
            self.assertNotIn("已经通过的正文", prepared.prompt)
            self.assertIn("review-invalid-", prepared.prompt)
            self.assertEqual(prepared.protected_count, 1)

            invalid.write_text('{"status":"pass"}\n', encoding="utf-8")
            passed.write_text("被模型误改", encoding="utf-8")
            finalized = coordinator.finalize()

            self.assertEqual(
                invalid.read_text(encoding="utf-8"),
                '{"status":"pass"}\n',
            )
            self.assertEqual(
                passed.read_text(encoding="utf-8"),
                "这段已经通过的正文不应进入 repair prompt。",
            )
            self.assertEqual(
                finalized["restored_outputs"],
                ["out/passed.md"],
            )

    def test_repair_context_carries_a_non_escalating_mechanical_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root, ("out/result.json",))
            sandbox = _sandbox(root)
            result = PreflightResult(
                False,
                (
                    PreflightIssue(
                        "invalid-json",
                        "out/result.json",
                        "JSON 无效。",
                        "只修复 JSON 格式。",
                    ),
                ),
            )
            coordinator = RepairContextCoordinator(
                task,
                sandbox,
                reasoning_budget=resolve_reasoning_budget(
                    ContextTaskKind.REVIEW,
                    "agent-required",
                ),
            )

            prepared = coordinator.prepare(result, 1, 2)
            payload = json.loads(prepared.artifact_path.read_text(encoding="utf-8"))

        reasoning = payload["budgets"]["reasoning"]
        self.assertEqual(reasoning["action"], "retry_same")
        self.assertEqual(reasoning["level"], "low")
        self.assertIn("机械格式", prepared.prompt)

    def test_issue_identity_is_stable_across_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root, ("out/result.json",))
            sandbox = _sandbox(root)
            output = sandbox.workspace / "out" / "result.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"status":"bad"}\n', encoding="utf-8")
            result = PreflightResult(
                False,
                (
                    PreflightIssue(
                        "invalid-status",
                        "out/result.json#status",
                        "状态错误。",
                        "修正状态。",
                    ),
                ),
            )
            coordinator = RepairContextCoordinator(task, sandbox)

            first = coordinator.prepare(result, 1, 2)
            first_payload = json.loads(
                first.artifact_path.read_text(encoding="utf-8")
            )
            coordinator.finalize()
            second = coordinator.prepare(result, 2, 2)
            second_payload = json.loads(
                second.artifact_path.read_text(encoding="utf-8")
            )
            coordinator.finalize()

            self.assertEqual(
                first_payload["issues"][0]["issue_id"],
                second_payload["issues"][0]["issue_id"],
            )
            self.assertNotEqual(
                first.context_digest,
                second.context_digest,
            )

    def test_excerpt_budgets_are_enforced_across_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = tuple(f"out/item-{index}.md" for index in range(7))
            task = _task(root, outputs)
            sandbox = _sandbox(root)
            for relative in outputs:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative + "\n" + "文" * 4_000, encoding="utf-8")
            result = PreflightResult(
                False,
                tuple(
                    PreflightIssue(
                        "text-invalid",
                        relative,
                        "文本不合格。",
                        "局部修订。",
                    )
                    for relative in outputs
                ),
            )
            coordinator = RepairContextCoordinator(task, sandbox)

            prepared = coordinator.prepare(result, 1, 2)
            payload = json.loads(
                prepared.artifact_path.read_text(encoding="utf-8")
            )
            coordinator.finalize()

            excerpts = payload["invalid_outputs"]
            self.assertLessEqual(
                sum(item["excerpt_characters"] for item in excerpts),
                MAX_TOTAL_EXCERPT_CHARACTERS,
            )
            self.assertTrue(
                all(
                    item["excerpt_characters"] <= MAX_EXCERPT_CHARACTERS
                    for item in excerpts
                )
            )

    def test_abstract_issue_uses_explicit_compatibility_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = ("out/a.md", "out/b.md")
            task = _task(root, outputs)
            sandbox = _sandbox(root)
            for relative in outputs:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")
            result = PreflightResult(
                False,
                (
                    PreflightIssue(
                        "cross-output-invalid",
                        "repair_targets",
                        "跨文件身份不一致。",
                        "复核所有声明产物。",
                    ),
                ),
            )
            coordinator = RepairContextCoordinator(task, sandbox)

            prepared = coordinator.prepare(result, 1, 2)
            coordinator.finalize()

            self.assertEqual(
                prepared.write_scope_mode,
                "all_declared_outputs_fallback",
            )
            self.assertEqual(prepared.target_count, 2)
            self.assertEqual(prepared.protected_count, 0)


if __name__ == "__main__":
    unittest.main()
