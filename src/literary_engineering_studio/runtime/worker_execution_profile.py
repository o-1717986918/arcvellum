"""Bind task execution profiles to one Worker run without owning execution."""

from __future__ import annotations

from pathlib import Path
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
        _bind_initial_pi_repair(task, sandbox, kwargs)
    return kwargs


def _bind_initial_pi_repair(
    task: TaskPackage,
    sandbox: SandboxManifest,
    kwargs: dict[str, Any],
) -> None:
    """Start formal revisions in read-before-write mode with a task-sized budget."""

    if task.task_type != "platform-agent-revision":
        return
    targets = _agent_repair_targets(task)
    if not targets:
        return
    existing = _existing_target_count(sandbox, targets)
    # Repair mode leases one deterministic read turn per existing target.
    # Compact targets may be batched, but correctness cannot depend on a model
    # fitting every replacement into one provider response.  Reserve one
    # write turn per Agent-owned target plus two transition/feedback turns.
    operation_floor = existing + len(targets) + 2
    turn_floor = max(2, operation_floor)
    tool_floor = max(2, operation_floor)
    kwargs["initial_repair_targets"] = targets
    kwargs["max_turns"] = max(int(kwargs.get("max_turns") or 0), turn_floor)
    kwargs["max_tool_calls"] = max(
        int(kwargs.get("max_tool_calls") or 0), tool_floor
    )
    _raise_provider_request_floor(kwargs, turn_floor)


def _agent_repair_targets(task: TaskPackage) -> tuple[str, ...]:
    declared = {
        str(item).replace("\\", "/")
        for item in task.payload.get("repair_targets") or []
        if str(item).strip()
    }
    return tuple(
        output.path
        for output in task.execution_contract.outputs
        if output.path in declared and output.kind == "agent-authored"
    )


def _existing_target_count(
    sandbox: SandboxManifest,
    targets: tuple[str, ...],
) -> int:
    return sum(
        (sandbox.workspace / Path(relative)).is_file()
        for relative in targets
    )


def _raise_provider_request_floor(
    kwargs: dict[str, Any],
    request_floor: int,
) -> None:
    budget = kwargs.get("reasoning_budget")
    if not isinstance(budget, dict):
        return
    normalized = dict(budget)
    normalized["max_provider_requests"] = max(
        int(normalized.get("max_provider_requests") or 0), request_floor
    )
    kwargs["reasoning_budget"] = normalized
