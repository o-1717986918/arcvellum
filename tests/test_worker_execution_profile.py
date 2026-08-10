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
        self.assertEqual(kwargs["reasoning_policy"], "medium")
        self.assertEqual(kwargs["max_turns"], 5)
        self.assertEqual(kwargs["max_tool_calls"], 5)
        self.assertNotIn("first_event_timeout", kwargs)
        self.assertEqual(profile.reasoning_budget_status, "shadow")
        self.assertEqual(profile.reasoning_budget_provider_support, "unsupported")
        self.assertEqual(observer.events[1][0], "runner.reasoning_budget.recommended")
        self.assertIsNone(
            observer.events[1][1]["reasoning_budget"]["effective"]
        )


if __name__ == "__main__":
    unittest.main()
