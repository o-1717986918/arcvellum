from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import (
    ContextBudgetExceeded,
    ContextBudgetMode,
    ContextTaskKind,
    resolve_task_context_budget,
)
from literary_engineering_studio.runtime.prompt_context import (
    build_prepared_prompt_context,
)


def _task(
    root: Path,
    *,
    task_type: str = "platform-agent",
    role: str = "main-agent",
    route: str = "scene-development",
    current_state: str = "structured-agent-task",
    outputs: tuple[str, ...] = ("workflow/result.json",),
) -> TaskPackage:
    payload = {
        "task_id": "scene-development-task",
        "route": route,
        "current_state": current_state,
        "task_type": task_type,
        "execution_policy": "agent-required",
        "agent_role": role,
        "runtime_capabilities_required": ["filesystem-read", "filesystem-write"],
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "expected_outputs": list(outputs),
        "output_contracts": [
            {
                "path": path,
                "kind": "semantic-candidate",
                "writeback_policy": "automatic",
            }
            for path in outputs
        ],
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


class ContextBudgetTests(unittest.TestCase):
    def test_default_shadow_budget_classifies_prose_without_changing_legacy_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                task_type="main-platform-agent-prose",
                role="main-creative-agent",
                current_state="generation-agent-task",
                outputs=("drafts/scenes/scene_0001.md",),
            )

            budget = resolve_task_context_budget(task)

            self.assertIs(budget.mode, ContextBudgetMode.SHADOW)
            self.assertIs(budget.task_kind, ContextTaskKind.PROSE)
            self.assertEqual(budget.target_inline_characters, 89_700)
            self.assertEqual(budget.enforced_inline_characters, 180_000)

    def test_shadow_reports_overage_without_truncating_to_the_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.md").write_text("文" * 80_000, encoding="utf-8")
            budget = resolve_task_context_budget(_task(root))

            prepared = build_prepared_prompt_context(
                root,
                ("source.md",),
                budget=budget,
            )

            self.assertEqual(prepared.included_paths, ("source.md",))
            self.assertIsNotNone(prepared.budget_report)
            report = prepared.budget_report
            assert report is not None
            self.assertGreater(report.first_turn_visible_characters, 72_000)
            self.assertEqual(report.budget_overage_count, 1)
            self.assertGreater(report.budget_overage_characters, 0)

    def test_high_risk_review_budget_preserves_real_mandatory_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            budget = resolve_task_context_budget(
                _task(
                    Path(temporary),
                    task_type="platform-agent-review",
                    role="main-review-agent",
                    current_state="candidate-review",
                )
            )

            self.assertIs(budget.task_kind, ContextTaskKind.REVIEW)
            self.assertEqual(budget.target_inline_characters, 65_550)
            self.assertEqual(budget.enforced_inline_characters, 180_000)

    def test_route_and_scene_semantics_take_priority_over_reviewer_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            planning = resolve_task_context_budget(
                _task(
                    root,
                    role="main-review-agent",
                    route="longform-planning",
                    current_state="budget-agent-task",
                )
            )
            roleplay = resolve_task_context_budget(
                _task(
                    root,
                    role="main-review-agent",
                    current_state="roleplay-agent-task",
                )
            )
            state = resolve_task_context_budget(
                _task(
                    root,
                    task_type="platform-agent-review",
                    role="main-review-agent",
                    current_state="state-agent-task",
                )
            )

            self.assertIs(planning.task_kind, ContextTaskKind.PLANNING)
            self.assertIs(roleplay.task_kind, ContextTaskKind.CREATIVE)
            self.assertIs(state.task_kind, ContextTaskKind.STRUCTURED)

    def test_bounded_mode_fails_closed_when_mandatory_context_does_not_fit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "required.md").write_text("x" * 80_000, encoding="utf-8")
            budget = resolve_task_context_budget(
                _task(root),
                {
                    "context_budget": {
                        "mode": "bounded",
                        "inline_limits": {"structured": 24_000},
                    }
                },
            )

            with self.assertRaisesRegex(
                ContextBudgetExceeded,
                "mandatory context exceeds",
            ):
                build_prepared_prompt_context(
                    root,
                    ("required.md",),
                    budget=budget,
                    mandatory_paths=("required.md",),
                )

    def test_invalid_mode_falls_back_to_shadow(self):
        with tempfile.TemporaryDirectory() as temporary:
            budget = resolve_task_context_budget(
                _task(Path(temporary)),
                {"context_budget": {"mode": "unknown-mode"}},
            )

            self.assertIs(budget.mode, ContextBudgetMode.SHADOW)


if __name__ == "__main__":
    unittest.main()
