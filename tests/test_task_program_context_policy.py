from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.task_program import (
    build_task_context,
    render_worker_program,
)


class _Envelope:
    def __init__(self, exact: list[str]):
        self.exact = exact

    def as_dict(self) -> dict[str, object]:
        return {
            "context_digest": "a" * 64,
            "character_budget": 57000,
            "must_inline": ["contract.json"],
            "exact_on_demand": list(self.exact),
            "summary_references": [],
            "excluded": [],
        }


class TaskProgramContextPolicyTests(unittest.TestCase):
    def test_task_context_uses_a_stable_non_path_project_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = build_task_context(_task(root))
            second = build_task_context(_task(root))

        self.assertEqual(first["project_id"], second["project_id"])
        self.assertRegex(str(first["project_id"]), r"^project-[0-9a-f]{16}$")
        self.assertNotIn(str(root), str(first["project_id"]))

    def test_exact_protected_sidecar_is_recovery_evidence_not_forced_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary))

            program = render_worker_program(
                task,
                prepared_context="{}",
                prepared_context_paths=("contract.json",),
                omitted_context_paths=("review.agent_tasks.md",),
                execution_context=_Envelope(["review.agent_tasks.md"]),
            )
            protected = program.split("## CLI Protected Outputs", 1)[1]

            self.assertIn("Exact On Demand 恢复证据", protected)
            self.assertIn("禁止主动读取 `.agent_tasks.md`", protected)
            self.assertIn("最小修复上下文", protected)
            self.assertNotIn("未内联的 CLI Protected Outputs 必须逐一读取", protected)

    def test_unclassified_protected_output_remains_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(Path(temporary))

            program = render_worker_program(
                task,
                execution_context=_Envelope([]),
            )
            protected = program.split("## CLI Protected Outputs", 1)[1]

            self.assertIn("未被 Execution Context 分类", protected)
            self.assertIn("必须逐一读取", protected)


def _task(root: Path) -> TaskPackage:
    payload = {
        "task_id": "scene-review",
        "route": "scene-development",
        "current_state": "candidate-review",
        "task_type": "platform-agent-review",
        "required_reading": [],
        "source_paths": ["contract.json", "review.agent_tasks.md"],
        "agent_source_paths": ["contract.json", "review.agent_tasks.md"],
        "expected_outputs": [
            "review.json",
            "review.agent_tasks.md",
        ],
        "core_managed_outputs": ["review.agent_tasks.md"],
        "validation_gates": [],
        "forbidden_shortcuts": [],
    }
    return TaskPackage(
        project_root=root,
        task_json_path=root / "task.json",
        task_markdown_path=root / "task.md",
        payload=payload,
    )


if __name__ == "__main__":
    unittest.main()
