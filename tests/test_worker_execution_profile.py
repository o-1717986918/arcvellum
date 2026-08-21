from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest

from literary_engineering_studio.contracts import TaskPackage
from literary_engineering_studio.runtime.execution_profiles import resolve_task_execution_profile
from literary_engineering_studio.runtime.sandbox import SandboxManifest
from literary_engineering_studio.runtime.worker_execution_profile import (
    activate_execution_profile,
    build_runtime_kwargs,
    persist_initial_execution_profile,
)


class _Runtime:
    def execution_control_capabilities(self):
        return ("bounded-repair", "silence-timeout-control")


class _PiWorkerRuntime:
    def execution_control_capabilities(self):
        return (
            "bounded-repair",
            "reasoning-budget-control",
            "provider-request-limit-control",
            "reasoning-policy-control",
            "turn-limit-control",
            "tool-limit-control",
        )


class _Observer:
    def __init__(self):
        self.events = []

    def emit(self, name, payload):
        self.events.append((name, payload))


class _Writeback:
    def validate_outputs(self, *_args, **_kwargs):
        return "valid"


def _task(root: Path) -> TaskPackage:
    payload = {
        "task_id": "scene-roleplay",
        "route": "scene-development",
        "current_state": "roleplay-agent-task",
        "task_type": "platform-agent",
        "execution_policy": "agent-required",
        "agent_role": "main-creative-agent",
        "runtime_capabilities_required": [],
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "expected_outputs": ["branches/result.json"],
        "output_contracts": [
            {
                "path": "branches/result.json",
                "kind": "semantic-candidate",
                "writeback_policy": "automatic",
            }
        ],
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


def _sandbox(root: Path) -> SandboxManifest:
    run = root / "run"
    workspace = run / "workspace"
    workspace.mkdir(parents=True)
    manifest = run / "run.json"
    manifest.write_text("{}\n", encoding="utf-8")
    return SandboxManifest(
        run_id="run",
        run_root=run,
        workspace=workspace,
        prompt_path=workspace / "AGENT_TASK.md",
        manifest_path=manifest,
        baseline_path=run / "baseline.json",
        expected_outputs=("branches/result.json",),
        control_workspace=run / "control-workspace",
        agent_workspace=workspace,
    )


def _project_revision_task(root: Path, count: int = 8) -> TaskPackage:
    targets = [f"scenes/scene_{index:04d}.yaml" for index in range(1, count + 1)]
    payload = {
        "task_id": "project-canon-revision",
        "route": "review-and-audit",
        "current_state": "canon-review-pass",
        "task_type": "platform-agent-revision",
        "execution_policy": "agent-required",
        "agent_role": "main-creative-agent",
        "runtime_capabilities_required": [
            "read-task-sources",
            "write-expected-outputs",
        ],
        "human_gate": {"required": False, "reasons": [], "source": "test"},
        "repair_targets": targets,
        "expected_outputs": [*targets, "reviews/agent/canon_review.json"],
        "output_contracts": [
            *[
                {
                    "path": path,
                    "kind": "agent-authored",
                    "writeback_policy": "preview-required",
                }
                for path in targets
            ],
            {
                "path": "reviews/agent/canon_review.json",
                "kind": "deterministic",
                "writeback_policy": "automatic",
            },
        ],
    }
    return TaskPackage(root, root / "task.json", root / "task.md", payload)


class WorkerExecutionProfileTests(unittest.TestCase):
    def test_shadow_profile_is_persisted_before_runtime_capabilities_are_known(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sandbox = _sandbox(root)
            persist_initial_execution_profile(
                _task(root),
                sandbox,
                {"timeout_seconds": 1800},
                "opencode",
            )
            profile = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))["execution_profile"]
        self.assertEqual(profile["mode"], "shadow")
        self.assertEqual(profile["controls"]["max_repair_attempts"]["status"], "pending")

    def test_canary_profile_drives_only_supported_runtime_kwargs(self):
        settings = {
            "timeout_seconds": 1800,
            "max_repair_attempts": 2,
            "execution_profile": {
                "enforcement": {"enabled": True, "task_kinds": ["creative"]}
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root)
            sandbox = _sandbox(root)
            observer = _Observer()
            profile, timeout = activate_execution_profile(
                task,
                sandbox,
                worker_config=settings,
                runtime_id="opencode",
                runtime=_Runtime(),
                observer=observer,
            )
            kwargs = build_runtime_kwargs(
                task,
                sandbox,
                runtime_id="opencode",
                timeout=timeout,
                profile=profile,
                worker_config=settings,
                observer=observer,
                cancel_event=threading.Event(),
                writeback=_Writeback(),
            )
        self.assertEqual(timeout, 600)
        self.assertEqual(kwargs["max_repairs"], 1)
        self.assertEqual(kwargs["first_event_timeout"], 180)
        self.assertEqual(kwargs["inter_event_timeout"], 300)
        self.assertNotIn("reasoning_policy", kwargs)
        self.assertEqual(observer.events[0][0], "runner.profile.resolved")

    def test_non_opencode_runtime_keeps_generic_execution_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root)
            sandbox = _sandbox(root)
            profile = resolve_task_execution_profile(
                task,
                {},
                runtime_id="host-agent",
                capability_ids=(),
            )
            kwargs = build_runtime_kwargs(
                task,
                sandbox,
                runtime_id="host-agent",
                timeout=1800,
                profile=profile,
                worker_config={},
                observer=_Observer(),
                cancel_event=threading.Event(),
                writeback=_Writeback(),
            )
        self.assertEqual(set(kwargs), {"timeout", "event_sink", "cancel_event"})

    def test_pi_worker_receives_supported_profile_controls(self):
        settings = {
            "timeout_seconds": 1800,
            "max_repair_attempts": 2,
            "execution_profile": {
                "enforcement": {"enabled": True, "task_kinds": ["creative"]}
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _task(root)
            sandbox = _sandbox(root)
            observer = _Observer()
            profile, timeout = activate_execution_profile(
                task,
                sandbox,
                worker_config=settings,
                runtime_id="pi-worker",
                runtime=_PiWorkerRuntime(),
                observer=observer,
            )
            kwargs = build_runtime_kwargs(
                task,
                sandbox,
                runtime_id="pi-worker",
                timeout=timeout,
                profile=profile,
                worker_config=settings,
                observer=observer,
                cancel_event=threading.Event(),
                writeback=_Writeback(),
            )

        self.assertEqual(timeout, 600)
        self.assertEqual(kwargs["max_repairs"], 1)
        self.assertEqual(kwargs["reasoning_policy"], "low")
        self.assertEqual(kwargs["reasoning_budget"]["maximum_level"], "medium")
        self.assertEqual(kwargs["reasoning_budget"]["total_tokens"], 2048)
        self.assertEqual(kwargs["max_turns"], 5)
        self.assertEqual(kwargs["max_tool_calls"], 5)
        self.assertNotIn("first_event_timeout", kwargs)
        self.assertEqual(profile.reasoning_budget_status, "applied")
        self.assertEqual(profile.reasoning_budget_provider_support, "unknown")
        self.assertEqual(observer.events[1][0], "runner.reasoning_budget.recommended")
        self.assertIsNotNone(
            observer.events[1][1]["reasoning_budget"]["effective"]
        )

    def test_pi_project_revision_starts_in_repair_mode_with_task_sized_budget(self):
        settings = {
            "timeout_seconds": 1800,
            "max_repair_attempts": 2,
            "execution_profile": {
                "enforcement": {"enabled": True, "task_kinds": ["review"]}
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = _project_revision_task(root)
            sandbox = _sandbox(root)
            for relative in task.payload["repair_targets"]:
                path = sandbox.workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("scene: complete\n", encoding="utf-8")
            observer = _Observer()
            profile, timeout = activate_execution_profile(
                task,
                sandbox,
                worker_config=settings,
                runtime_id="pi-worker",
                runtime=_PiWorkerRuntime(),
                observer=observer,
            )
            kwargs = build_runtime_kwargs(
                task,
                sandbox,
                runtime_id="pi-worker",
                timeout=timeout,
                profile=profile,
                worker_config=settings,
                observer=observer,
                cancel_event=threading.Event(),
                writeback=_Writeback(),
            )

        self.assertEqual(
            kwargs["initial_repair_targets"],
            tuple(task.payload["repair_targets"]),
        )
        self.assertGreaterEqual(kwargs["max_turns"], 18)
        self.assertGreaterEqual(kwargs["max_tool_calls"], 18)
        self.assertGreaterEqual(
            kwargs["reasoning_budget"]["max_provider_requests"], 18
        )


if __name__ == "__main__":
    unittest.main()
