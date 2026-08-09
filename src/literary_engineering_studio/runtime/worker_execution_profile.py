"""Bind task execution profiles to one Worker run without owning execution."""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts import TaskPackage
from .execution_profiles import TaskExecutionProfile, resolve_task_execution_profile
from .repair_context import RepairContextCoordinator
from .sandbox import SandboxManifest, update_run_manifest


def persist_initial_execution_profile(
    task: TaskPackage,
    sandbox: SandboxManifest,
    worker_config: Mapping[str, Any],
    runtime_id: str,
) -> None:
    profile = resolve_task_execution_profile(task, worker_config, runtime_id=runtime_id)
    if sandbox.manifest_path.is_file():
        update_run_manifest(sandbox.manifest_path, execution_profile=profile.as_dict())


def activate_execution_profile(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    worker_config: Mapping[str, Any],
    runtime_id: str,
    runtime: Any,
    observer: Any,
) -> tuple[TaskExecutionProfile, int]:
    profile = resolve_task_execution_profile(
        task,
        worker_config,
        runtime_id=runtime_id,
        capability_ids=runtime.execution_control_capabilities(),
    )
    if sandbox.manifest_path.is_file():
        update_run_manifest(sandbox.manifest_path, execution_profile=profile.as_dict())
    observer.emit(
        "runner.profile.resolved",
        {
            "runner_id": runtime_id,
            "task_id": task.task_id,
            "execution_profile": profile.as_dict(),
        },
    )
    timeout = profile.effective_int(
        "total_timeout_seconds",
        int(worker_config.get("timeout_seconds") or 1800),
    )
    return profile, timeout


def profile_runtime_kwargs(
    profile: TaskExecutionProfile,
    worker_config: Mapping[str, Any],
) -> dict[str, int]:
    kwargs = {
        "max_repairs": profile.effective_int(
            "max_repair_attempts",
            int(worker_config.get("max_repair_attempts") or 2),
        )
    }
    if profile.is_applied("first_event_timeout_seconds"):
        kwargs["first_event_timeout"] = profile.effective_int("first_event_timeout_seconds", 180)
    if profile.is_applied("inter_event_timeout_seconds"):
        kwargs["inter_event_timeout"] = profile.effective_int("inter_event_timeout_seconds", 300)
    return kwargs


def build_runtime_kwargs(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    runtime_id: str,
    timeout: int,
    profile: TaskExecutionProfile,
    worker_config: Mapping[str, Any],
    observer: Any,
    cancel_event: Any,
    writeback: Any,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "event_sink": observer.emit,
        "cancel_event": cancel_event,
    }
    if runtime_id != "opencode":
        return kwargs
    repair_context = RepairContextCoordinator(task, sandbox)
    kwargs.update(
        {
            "output_validator": lambda: writeback.validate_outputs(
                task,
                sandbox,
                runtime_id=runtime_id,
            ),
            "repair_prompt_builder": repair_context.prepare,
            "repair_turn_finalizer": repair_context.finalize,
            **profile_runtime_kwargs(profile, worker_config),
        }
    )
    return kwargs
