from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.context_budget import ContextTaskKind
from literary_engineering_studio.runtime.execution_profiles import (
    ExecutionProfileError,
    resolve_task_execution_profile,
)


def _task(
    root: Path,
    *,
    route: str = "scene-development",
    state: str = "roleplay-agent-task",
    task_type: str = "platform-agent",
    role: str = "main-creative-agent",
    policy: str = "agent-required",
) -> TaskPackage:
    payload = {
        "task_id": f"{route}-{state}",
        "route": route,
        "current_state": state,
        "task_type": task_type,
        "execution_policy": policy,
        "agent_role": role,
        "runtime_capabilities_required": [],
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "expected_outputs": ["workflow/result.json"],
        "output_contracts": [
            {
                "path": "workflow/result.json",
                "kind": "semantic-candidate",
                "writeback_policy": "automatic",
            }
        ],
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


def _controls(profile) -> dict[str, dict[str, object]]:
    return profile.as_dict()["controls"]


class ExecutionProfileTests(unittest.TestCase):
    def test_profile_reuses_all_canonical_context_task_kinds(self):
        cases = (
            ("scene-development", "candidate-generation-provenance", "main-platform-agent-prose", "main-creative-agent", ContextTaskKind.PROSE),
            ("scene-development", "candidate-review", "platform-agent-review", "main-review-agent", ContextTaskKind.REVIEW),
            ("source-ingest", "archaeology-agent-task", "platform-agent", "main-agent", ContextTaskKind.ARCHAEOLOGY),
            ("style-learning", "style-agent-task", "platform-agent", "main-agent", ContextTaskKind.STYLE),
            ("longform-planning", "story-architecture-agent-task", "platform-agent", "main-agent", ContextTaskKind.PLANNING),
            ("scene-development", "roleplay-agent-task", "platform-agent", "main-creative-agent", ContextTaskKind.CREATIVE),
            ("scene-development", "state-agent-task", "platform-agent-review", "main-review-agent", ContextTaskKind.STRUCTURED),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for route, state, task_type, role, expected in cases:
                with self.subTest(expected=expected.value):
                    actual = resolve_task_execution_profile(
                    _task(root, route=route, state=state, task_type=task_type, role=role),
                    {},
                    runtime_id="opencode",
                    ).task_kind
                    self.assertIs(actual, expected)

    def test_default_shadow_preserves_legacy_timeout_and_repair_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = resolve_task_execution_profile(
                _task(Path(temporary)),
                {"timeout_seconds": 1800, "max_repair_attempts": 2},
                runtime_id="opencode",
                capability_ids=("bounded-repair", "silence-timeout-control"),
            )
        controls = _controls(profile)
        projection = profile.as_dict()
        self.assertEqual(profile.mode, "shadow")
        self.assertEqual(projection["schema"], "arcvellum/task-execution-profile/v2")
        self.assertIn("arcvellum/task-execution-profile/v1", projection["compatible_with"])
        self.assertEqual(profile.safe_projection_v1()["schema"], "arcvellum/task-execution-profile/v1")
        self.assertEqual(
            projection["reasoning_budget"]["requested"]["initial_level"],
            "low",
        )
        self.assertEqual(projection["reasoning_budget"]["status"], "shadow")
        self.assertEqual(projection["reasoning_budget"]["provider_support"], "unsupported")
        self.assertIsNone(projection["reasoning_budget"]["effective"])
        self.assertEqual(controls["total_timeout_seconds"]["effective"], 1800)
        self.assertEqual(controls["max_repair_attempts"]["effective"], 2)
        self.assertEqual(controls["first_event_timeout_seconds"]["status"], "shadow")
        self.assertEqual(controls["reasoning_policy"]["status"], "unsupported")

    def test_enforcement_applies_only_controls_supported_by_runtime(self):
        settings = {
            "timeout_seconds": 1800,
            "max_repair_attempts": 2,
            "execution_profile": {
                "mode": "shadow",
                "enforcement": {
                    "enabled": True,
                    "runtimes": ["opencode"],
                    "routes": ["scene-development"],
                    "task_kinds": ["creative"],
                },
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            profile = resolve_task_execution_profile(
                _task(Path(temporary)),
                settings,
                runtime_id="opencode",
                capability_ids=("bounded-repair", "silence-timeout-control"),
            )
        controls = _controls(profile)
        self.assertEqual(profile.mode, "enforced")
        self.assertEqual(controls["total_timeout_seconds"]["effective"], 600)
        self.assertEqual(controls["max_repair_attempts"]["effective"], 1)
        self.assertEqual(controls["first_event_timeout_seconds"]["effective"], 180)
        self.assertEqual(controls["inter_event_timeout_seconds"]["effective"], 300)
        self.assertEqual(controls["max_turns"]["status"], "unsupported")
        self.assertEqual(controls["max_tool_calls"]["status"], "unsupported")

    def test_prose_role_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = _task(
                Path(temporary),
                state="candidate-generation-provenance",
                task_type="main-platform-agent-prose",
                role="main-review-agent",
            )
            with self.assertRaisesRegex(ExecutionProfileError, "main-creative-agent"):
                resolve_task_execution_profile(task, {}, runtime_id="opencode")

    def test_deterministic_profile_has_no_agent_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = resolve_task_execution_profile(
                _task(Path(temporary), policy="deterministic", role="deterministic-engine"),
                {},
                runtime_id="opencode",
            )
        self.assertEqual(profile.mode, "deterministic")
        budget = profile.as_dict()["reasoning_budget"]
        self.assertEqual(budget["requested"]["total_tokens"], 0)
        self.assertEqual(budget["status"], "applied")
        for control in _controls(profile).values():
            self.assertEqual(control["effective"], 0 if control["requested"] != "off" else "off")
            self.assertEqual(control["status"], "applied")


if __name__ == "__main__":
    unittest.main()
