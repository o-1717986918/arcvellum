"""Task selection, sandbox staging, and core-command preparation for Agent Worker."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Mapping

from ..contracts import TaskPackage
from ..core_bridge import CoreBridge, task_command_parameters
from .context_budget import TaskContextBudget, resolve_task_context_budget
from .execution_profiles import TaskExecutionProfile
from .prepared_context_cache import PreparedContextCache
from .sandbox import (
    SandboxManifest,
    capture_core_managed_outputs,
    materialize_agent_workspace,
    update_run_manifest,
)
from .worker_execution_profile import (
    prompt_program_settings,
    stage_profiled_task,
)
from .worker_observability import WorkerObserver
from .worker_paths import validate_project
from .worker_results import WorkerRunResult


TaskSelector = Callable[..., tuple[TaskPackage | None, str]]
PreparationResult = tuple[
    TaskPackage | None,
    SandboxManifest | None,
    WorkerRunResult | None,
]


def prepare_worker_task(
    project_root: Path,
    *,
    route: str,
    runtime_id: str,
    task_id: str,
    scene: str,
    config: dict[str, Any],
    bridge: CoreBridge,
    observer: WorkerObserver,
    select_task: TaskSelector,
    prepared_context_cache: PreparedContextCache | None,
) -> PreparationResult:
    """Prepare exactly one state-machine task without owning its execution lifecycle."""
    observer.reset_context_ledger()
    project = validate_project(project_root)
    observer.emit("task.selecting", {"project_root": str(project), "route": route})
    task, ready_message = select_task(
        project,
        route=route,
        task_id=task_id,
        scene=scene,
        emit_binding_events=True,
    )
    if task is None:
        return None, None, _route_ready(project, route, runtime_id, ready_message)

    observer.emit("task.opened", _task_opened_payload(task))
    if task.human_gate_reasons:
        return task, None, _human_gate_result(task, project, runtime_id, observer)

    worker_config = config.get("worker", {})
    context_budget = resolve_task_context_budget(task, worker_config)
    profile, sandbox, active_runtime = _stage_sandbox(
        task,
        runtime_id=runtime_id,
        worker_config=worker_config,
        observer=observer,
        context_budget=context_budget,
        prepared_context_cache=prepared_context_cache,
    )
    terminal = _run_core_command(
        task,
        sandbox,
        project=project,
        requested_runtime=runtime_id,
        active_runtime=active_runtime,
        bridge=bridge,
        observer=observer,
        context_budget=context_budget,
        execution_profile=profile.as_dict(),
        worker_config=worker_config,
        prepared_context_cache=prepared_context_cache,
    )
    if terminal is not None:
        return task, terminal[0], terminal[1]

    observer.publish_context_ready(task, sandbox, active_runtime)
    return task, sandbox, None


def _route_ready(
    project: Path,
    route: str,
    runtime_id: str,
    message: str,
) -> WorkerRunResult:
    return WorkerRunResult(
        "route_ready",
        project,
        route,
        "",
        runtime_id,
        None,
        None,
        message or "route has no pending task",
        audit_fields={"status": "route-ready", "scope": "route-terminal-scan"},
    )


def _human_gate_result(
    task: TaskPackage,
    project: Path,
    runtime_id: str,
    observer: WorkerObserver,
) -> WorkerRunResult:
    reasons = list(task.human_gate_reasons)
    observer.emit("human.required", {"reasons": reasons, "task_id": task.task_id})
    return WorkerRunResult(
        "waiting_human",
        project,
        task.route,
        task.task_id,
        runtime_id,
        None,
        None,
        "human approval gate: " + ", ".join(reasons),
    )


def _stage_sandbox(
    task: TaskPackage,
    *,
    runtime_id: str,
    worker_config: Mapping[str, Any],
    observer: WorkerObserver,
    context_budget: TaskContextBudget,
    prepared_context_cache: PreparedContextCache | None,
) -> tuple[TaskExecutionProfile, SandboxManifest, str]:
    runs_root = Path(str(worker_config.get("runs_root") or ""))
    profile, sandbox = stage_profiled_task(
        task,
        runs_root,
        worker_config=worker_config,
        runtime_id=runtime_id,
        materialize_agent_view=_materialize_agent_view_immediately(task),
        context_budget=context_budget,
        prepared_context_cache=prepared_context_cache,
    )
    active_runtime = (
        "deterministic-engine"
        if task.execution_contract.execution_policy == "deterministic"
        else runtime_id
    )
    observer.bind_run_root(sandbox.run_root)
    observer.emit(
        "sandbox.prepared",
        {
            "run_id": sandbox.run_id,
            "run_root": str(sandbox.run_root),
            "workspace": str(sandbox.workspace),
            "control_workspace": str(sandbox.control_workspace or sandbox.workspace),
            "project_root": str(task.project_root),
            "runner_id": active_runtime,
            "task_id": task.task_id,
        },
    )
    return profile, sandbox, active_runtime


def _run_core_command(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    project: Path,
    requested_runtime: str,
    active_runtime: str,
    bridge: CoreBridge,
    observer: WorkerObserver,
    context_budget: TaskContextBudget,
    execution_profile: dict[str, Any],
    worker_config: Mapping[str, Any],
    prepared_context_cache: PreparedContextCache | None,
) -> tuple[SandboxManifest | None, WorkerRunResult] | None:
    if not task.command:
        return None
    unresolved = task_command_parameters(task.command)
    if unresolved:
        return None, _parameters_required_result(
            task,
            project=project,
            runtime_id=requested_runtime,
            parameters=unresolved,
            observer=observer,
        )

    observer.emit("core.command_started", {"task_id": task.task_id})
    try:
        command_result = bridge.execute_task_command(
            task.command,
            sandbox.control_workspace or sandbox.workspace,
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        update_run_manifest(
            sandbox.manifest_path,
            status="core_command_failed",
            core_command_error=str(exc),
        )
        observer.emit("core.command_failed", {"task_id": task.task_id, "error": str(exc)})
        return sandbox, WorkerRunResult(
            "core_command_failed",
            project,
            task.route,
            task.task_id,
            active_runtime,
            sandbox.run_root,
            sandbox.workspace,
            str(exc),
        )

    _complete_core_command_preparation(
        task,
        sandbox,
        returncode=command_result.returncode,
        observer=observer,
        context_budget=context_budget,
        execution_profile=execution_profile,
        worker_config=worker_config,
        prepared_context_cache=prepared_context_cache,
    )
    return None


def _parameters_required_result(
    task: TaskPackage,
    *,
    project: Path,
    runtime_id: str,
    parameters: tuple[str, ...],
    observer: WorkerObserver,
) -> WorkerRunResult:
    message = "当前任务需要先确定：" + "、".join(parameters)
    observer.emit(
        "task.parameters_required",
        {"task_id": task.task_id, "parameters": list(parameters), "message": message},
    )
    return WorkerRunResult(
        "waiting_human",
        project,
        task.route,
        task.task_id,
        runtime_id,
        None,
        None,
        message,
    )


def _complete_core_command_preparation(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    returncode: int,
    observer: WorkerObserver,
    context_budget: TaskContextBudget,
    execution_profile: dict[str, Any],
    worker_config: Mapping[str, Any],
    prepared_context_cache: PreparedContextCache | None,
) -> None:
    update_run_manifest(
        sandbox.manifest_path,
        status="core_command_completed",
        core_command_returncode=returncode,
    )
    protected = capture_core_managed_outputs(task, sandbox)
    if protected:
        observer.emit(
            "core.outputs_protected",
            {"task_id": task.task_id, "paths": list(protected)},
        )
    if task.execution_contract.execution_policy == "agent-required":
        visible = materialize_agent_workspace(
            task,
            sandbox,
            context_budget=context_budget,
            prepared_context_cache=prepared_context_cache,
            execution_profile=execution_profile,
            prompt_program_config=prompt_program_settings(worker_config),
        )
        observer.emit(
            "sandbox.agent_workspace_ready",
            {"task_id": task.task_id, "visible_count": len(visible)},
        )
    observer.emit(
        "core.command_completed",
        {"task_id": task.task_id, "returncode": returncode},
    )


def _materialize_agent_view_immediately(task: TaskPackage) -> bool:
    return (
        task.execution_contract.execution_policy == "agent-required"
        and not task.command
    )


def _task_opened_payload(task: TaskPackage) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "scene_id": str(task.payload.get("scene_id") or ""),
        "agent_role": task.execution_contract.agent_role,
        "execution_contract": task.execution_contract.as_dict(),
    }


__all__ = ["PreparationResult", "prepare_worker_task"]
