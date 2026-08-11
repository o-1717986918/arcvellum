"""Bind task execution profiles to one Worker run without owning execution."""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts import TaskPackage
from .execution_profiles import TaskExecutionProfile, resolve_task_execution_profile
from .repair_context import RepairContextCoordinator
from .progress_policy import build_runtime_progress_digest
from .sandbox import SandboxManifest, stage_task, update_run_manifest


def stage_profiled_task(
    task: TaskPackage,
    runs_root,
    *,
    worker_config: Mapping[str, Any],
    runtime_id: str,
    materialize_agent_view: bool,
    context_budget,
    prepared_context_cache,
) -> tuple[TaskExecutionProfile, SandboxManifest]:
    profile = resolve_task_execution_profile(task, worker_config, runtime_id=runtime_id)
    sandbox = stage_task(
        task,
        runs_root,
        runtime=(
            "deterministic-engine"
            if task.execution_contract.execution_policy == "deterministic"
            else runtime_id
        ),
        materialize_agent_view=materialize_agent_view,
        context_budget=context_budget,
        prepared_context_cache=prepared_context_cache,
        execution_profile=profile.as_dict(),
        prompt_program_config=prompt_program_settings(worker_config),
    )
    persist_initial_execution_profile(
        task, sandbox, worker_config, runtime_id, profile=profile
    )
    return profile, sandbox


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def prompt_program_settings(worker_config: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(worker_config.get("prompt_program"))


def persist_initial_execution_profile(
    task: TaskPackage,
    sandbox: SandboxManifest,
    worker_config: Mapping[str, Any],
    runtime_id: str,
    *,
    profile: TaskExecutionProfile | None = None,
) -> TaskExecutionProfile:
    resolved = profile or resolve_task_execution_profile(task, worker_config, runtime_id=runtime_id)
    if sandbox.manifest_path.is_file():
        update_run_manifest(sandbox.manifest_path, execution_profile=resolved.as_dict())
    return resolved


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
    observer.emit(
        "runner.reasoning_budget.recommended",
        {
            "runner_id": runtime_id,
            "task_id": task.task_id,
            "reasoning_budget": profile.as_dict()["reasoning_budget"],
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
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "max_repairs": profile.effective_int(
            "max_repair_attempts",
            int(worker_config.get("max_repair_attempts") or 2),
        )
    }
    if profile.is_applied("first_event_timeout_seconds"):
        kwargs["first_event_timeout"] = profile.effective_int("first_event_timeout_seconds", 180)
    if profile.is_applied("inter_event_timeout_seconds"):
        kwargs["inter_event_timeout"] = profile.effective_int("inter_event_timeout_seconds", 300)
    if profile.is_applied("reasoning_policy"):
        kwargs["reasoning_policy"] = profile.effective_str("reasoning_policy", "low")
    if profile.reasoning_budget_status == "applied":
        kwargs["reasoning_policy"] = profile.reasoning_budget.initial_level
        kwargs["reasoning_budget"] = profile.reasoning_budget.as_dict()
    if profile.is_applied("max_turns"):
        kwargs["max_turns"] = profile.effective_int("max_turns", 6)
    if profile.is_applied("max_tool_calls"):
        kwargs["max_tool_calls"] = profile.effective_int("max_tool_calls", 12)
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
    if runtime_id not in {"opencode", "pi-worker"}:
        return kwargs
    repair_context = RepairContextCoordinator(
        task,
        sandbox,
        reasoning_budget=profile.reasoning_budget,
        same_session_required=runtime_id == "opencode",
    )
    kwargs.update(
        {
            "output_validator": lambda: writeback.validate_outputs(
                task,
                sandbox,
                runtime_id=runtime_id,
            ),
            "repair_prompt_builder": repair_context.prepare,
            "repair_turn_finalizer": repair_context.finalize,
            "progress_digest_builder": lambda preflight, context_access: build_runtime_progress_digest(
                task,
                sandbox,
                preflight,
                context_access=context_access,
            ).event_fields(),
            **profile_runtime_kwargs(profile, worker_config),
        }
    )
    if runtime_id == "pi-worker":
        kwargs["allowed_states"] = (task.current_state,)
    return kwargs
