"""Formal Agent Worker bound to the Literary Engineering CLI state machine."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any
from collections.abc import Callable

from ..application.config import load_config
from ..contracts import TaskPackage, load_task_package
from ..core_bridge import CoreBridge, task_command_parameters
from ..orchestration.active_plan import ActivePlanLoader
from ..orchestration.project_fingerprint import planning_project_fingerprint
from ..orchestration.scene_binding import bind_scene_task
from ..orchestration.settings import OrchestrationMode, orchestration_settings
from ..persistence.job_store import JobStore
from ..runtimes import build_runtime
from .context_budget import resolve_task_context_budget
from .repair_context import RepairContextCoordinator
from .sandbox import (
    SandboxManifest,
    capture_core_managed_outputs,
    changed_agent_outputs,
    materialize_agent_workspace,
    sandbox_from_run,
    stage_task,
    update_run_manifest,
)
from .run_manifest import load_run
from .task_snapshot import load_run_task_snapshot
from .worker_observability import WorkerObserver
from .worker_paths import (
    resolve_task_json_path as _resolve_task_json_path,
    validate_project as _validate_project,
)
from .worker_results import WorkerRunResult
from .worker_writeback import WritebackCoordinator


def _materialize_agent_view_immediately(task: TaskPackage) -> bool:
    return task.execution_contract.execution_policy == "agent-required" and not task.command


def _task_opened_payload(task: TaskPackage) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "scene_id": str(task.payload.get("scene_id") or ""),
        "agent_role": task.execution_contract.agent_role,
        "execution_contract": task.execution_contract.as_dict(),
    }


class AgentWorker:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
        runtime_pool=None,
        plan_store=None,
        orchestration_fingerprint_provider: Callable[[Path], str] | None = None,
    ):
        self.config = config or load_config()
        self.bridge = CoreBridge(self.config)
        self.event_sink = event_sink
        self.observer = WorkerObserver(event_sink)
        self.writeback = WritebackCoordinator(self.bridge, self.observer)
        self.cancel_event = cancel_event or threading.Event()
        self.runtime_pool = runtime_pool
        self.plan_store = plan_store
        self.orchestration_fingerprint_provider = (
            orchestration_fingerprint_provider or planning_project_fingerprint
        )

    def approve_writeback(self, run_root: Path, *, approved_by: str) -> WorkerRunResult:
        return self.writeback.approve_writeback(run_root, approved_by=approved_by)

    def reject_writeback(
        self,
        run_root: Path,
        *,
        rejected_by: str,
        reason: str = "",
    ) -> WorkerRunResult:
        return self.writeback.reject_writeback(
            run_root,
            rejected_by=rejected_by,
            reason=reason,
        )

    def prepare(
        self, project_root: Path, *, route: str, runtime_id: str,
        task_id: str = "", scene: str = "",
    ) -> tuple[TaskPackage | None, SandboxManifest | None, WorkerRunResult | None]:
        self.observer.reset_context_ledger()
        project = _validate_project(project_root)
        self.observer.emit("task.selecting", {"project_root": str(project), "route": route})
        selected_task_id = task_id.strip()
        if not selected_task_id:
            issued = self.bridge.task_next(project, route, scene=scene)
            if issued.fields.get("status") == "ready" or not issued.fields.get("task_id"):
                return None, None, WorkerRunResult(
                    "route_ready",
                    project,
                    route,
                    "",
                    runtime_id,
                    None,
                    None,
                    issued.fields.get("message", "route has no pending task"),
                    audit_fields={"status": "route-ready", "scope": "route-terminal-scan"},
                )
            selected_task_id = issued.fields["task_id"]

        opened = self.bridge.task_open(project, selected_task_id)
        task_json_path = _resolve_task_json_path(project, selected_task_id, opened.fields.get("task_json", ""))
        task = load_task_package(project, task_json_path)
        task = self._bind_active_scene_plan(task)
        context_budget = resolve_task_context_budget(task, self.config.get("worker"))
        self.observer.emit("task.opened", _task_opened_payload(task))
        if task.human_gate_reasons:
            self.observer.emit("human.required", {"reasons": list(task.human_gate_reasons), "task_id": task.task_id})
            return task, None, WorkerRunResult(
                "waiting_human",
                project,
                task.route,
                task.task_id,
                runtime_id,
                None,
                None,
                "human approval gate: " + ", ".join(task.human_gate_reasons),
            )

        runs_root = Path(str(self.config.get("worker", {}).get("runs_root") or ""))
        active_runtime = "deterministic-engine" if task.execution_contract.execution_policy == "deterministic" else runtime_id
        sandbox = stage_task(
            task, runs_root, runtime=active_runtime,
            materialize_agent_view=_materialize_agent_view_immediately(task),
            context_budget=context_budget,
        )
        self.observer.bind_run_root(sandbox.run_root)
        self.observer.emit(
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
        if task.command:
            unresolved = task_command_parameters(task.command)
            if unresolved:
                message = "当前任务需要先确定：" + "、".join(unresolved)
                self.observer.emit(
                    "task.parameters_required",
                    {"task_id": task.task_id, "parameters": list(unresolved), "message": message},
                )
                return task, None, WorkerRunResult(
                    "waiting_human",
                    project,
                    task.route,
                    task.task_id,
                    runtime_id,
                    None,
                    None,
                    message,
                )
            self.observer.emit("core.command_started", {"task_id": task.task_id})
            try:
                command_result = self.bridge.execute_task_command(task.command, sandbox.control_workspace or sandbox.workspace)
            except (RuntimeError, ValueError, FileNotFoundError) as exc:
                update_run_manifest(
                    sandbox.manifest_path,
                    status="core_command_failed",
                    core_command_error=str(exc),
                )
                self.observer.emit("core.command_failed", {"task_id": task.task_id, "error": str(exc)})
                return task, sandbox, WorkerRunResult(
                    "core_command_failed",
                    project,
                    task.route,
                    task.task_id,
                    active_runtime,
                    sandbox.run_root,
                    sandbox.workspace,
                    str(exc),
                )
            update_run_manifest(
                sandbox.manifest_path,
                status="core_command_completed",
                core_command_returncode=command_result.returncode,
            )
            protected = capture_core_managed_outputs(task, sandbox)
            if protected:
                self.observer.emit("core.outputs_protected", {"task_id": task.task_id, "paths": list(protected)})
            if task.execution_contract.execution_policy == "agent-required":
                visible = materialize_agent_workspace(task, sandbox, context_budget=context_budget)
                self.observer.emit("sandbox.agent_workspace_ready", {"task_id": task.task_id, "visible_count": len(visible)})
            self.observer.emit("core.command_completed", {"task_id": task.task_id, "returncode": command_result.returncode})
        self.observer.publish_context_ready(task, sandbox, active_runtime)
        return task, sandbox, None

    def _bind_active_scene_plan(self, task: TaskPackage) -> TaskPackage:
        settings = orchestration_settings(self.config)
        if settings.effective_mode in {
            OrchestrationMode.FIXED,
            OrchestrationMode.SHADOW,
        }:
            return task
        if task.route != "scene-development" or not str(
            task.payload.get("scene_id") or ""
        ).strip():
            return task
        store = self.plan_store
        if store is None:
            application = self.config.get("application")
            payload = application if isinstance(application, dict) else {}
            store = JobStore(Path(str(payload.get("database_path") or "studio.sqlite3")))
        try:
            active = ActivePlanLoader(
                store,
                fingerprint_provider=self.orchestration_fingerprint_provider,
            ).load(task.project_root)
            if active is None:
                self.observer.emit(
                    "orchestration.fixed_fallback",
                    {"task_id": task.task_id, "reason": "no-active-plan"},
                )
                return task
            binding = bind_scene_task(
                task,
                plan=active.plan,
                graph=active.graph,
                current_project_fingerprint=active.project_fingerprint,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            self.observer.emit(
                "orchestration.fixed_fallback",
                {"task_id": task.task_id, "reason": str(exc)},
            )
            return task
        self.observer.emit(
            "orchestration.plan_bound",
            {
                "task_id": task.task_id,
                "plan_id": binding.plan_id,
                "plan_revision": binding.plan_revision,
                "node_id": binding.node_id,
                "node_kind": binding.node_kind,
                "binding_status": binding.status,
            },
        )
        return binding.task

    def run_once(
        self,
        project_root: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str = "",
        scene: str = "",
    ) -> WorkerRunResult:
        task, sandbox, terminal = self.prepare(
            project_root,
            route=route,
            runtime_id=runtime_id,
            task_id=task_id,
            scene=scene,
        )
        if terminal is not None:
            return terminal
        assert task is not None and sandbox is not None
        active_runtime = "deterministic-engine" if task.execution_contract.execution_policy == "deterministic" else runtime_id

        if task.execution_contract.execution_policy == "deterministic":
            self.observer.emit("runner.skipped", {"reason": "deterministic-cli", "task_id": task.task_id})
            update_run_manifest(
                sandbox.manifest_path,
                status="deterministic_outputs_ready",
                runtime_message="core deterministic command completed in the isolated workspace",
                runtime_returncode=0,
            )
            return self.writeback.complete_outputs(task, sandbox, active_runtime)

        if self.cancel_event.is_set():
            self.observer.emit("run.cancelled", {"stage": "before-runner"})
            return WorkerRunResult(
                "cancelled",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                "run cancelled before Agent Runner execution",
            )

        runtime = build_runtime(runtime_id, self.config, runtime_pool=self.runtime_pool)
        timeout = int(self.config.get("worker", {}).get("timeout_seconds") or 1800)
        self.observer.emit("runner.started", {"runner_id": runtime_id, "task_id": task.task_id})
        runtime_kwargs = {
            "timeout": timeout,
            "event_sink": self.observer.emit,
            "cancel_event": self.cancel_event,
        }
        if runtime_id == "opencode":
            repair_context = RepairContextCoordinator(task, sandbox)

            def validate_outputs():
                return self.writeback.validate_outputs(
                    task,
                    sandbox,
                    runtime_id=runtime_id,
                )

            runtime_kwargs.update(
                {
                    "output_validator": validate_outputs,
                    "max_repairs": int(self.config.get("worker", {}).get("max_repair_attempts") or 2),
                    "repair_prompt_builder": repair_context.prepare,
                    "repair_turn_finalizer": repair_context.finalize,
                }
            )
        runtime_result = runtime.execute(
            sandbox.workspace,
            sandbox.prompt_path,
            sandbox.run_root,
            **runtime_kwargs,
        )
        self.observer.emit(
            "runner.completed",
            {
                "runner_id": runtime_id,
                "status": runtime_result.status,
                "returncode": runtime_result.returncode,
            },
        )
        update_run_manifest(
            sandbox.manifest_path,
            status=runtime_result.status,
            runtime_message=runtime_result.message,
            runtime_returncode=runtime_result.returncode,
            runtime_output=str(runtime_result.output_path) if runtime_result.output_path else "",
            runtime_metadata=runtime_result.metadata or {},
        )
        if runtime_result.status == "waiting_host_agent":
            return WorkerRunResult(
                runtime_result.status,
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                runtime_result.message,
            )
        if runtime_result.status != "completed":
            return WorkerRunResult(
                "runtime_failed",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                runtime_result.message,
            )

        if self.cancel_event.is_set():
            self.observer.emit("run.cancelled", {"stage": "before-writeback"})
            return WorkerRunResult(
                "cancelled",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                "run cancelled before formal writeback",
            )

        return self.writeback.complete_outputs(task, sandbox, runtime_id)

    def resume_from_run(self, run_root: Path) -> WorkerRunResult:
        """Resume a timed-out run only when it contains fresh valid Agent output."""
        run = load_run(run_root)
        self.observer.bind_context_ledger(run)
        project = _validate_project(Path(str(run.get("project_root") or "")))
        task = load_run_task_snapshot(
            run_root,
            project_root=project,
            manifest=run,
        )
        sandbox = sandbox_from_run(run_root)
        if str(run.get("task_id") or "") != task.task_id:
            raise ValueError("recovery sandbox task identity does not match its task package")

        self.observer.emit("run.resume_started", {"run_root": str(sandbox.run_root), "task_id": task.task_id})
        changed_outputs = changed_agent_outputs(sandbox)
        if not changed_outputs:
            message = "recovery requires fresh Agent-authored expected outputs; the sandbox only contains staged or stale files"
            update_run_manifest(
                sandbox.manifest_path,
                recovery={"status": "rejected", "reason": "no-fresh-agent-output"},
            )
            self.observer.emit("run.resume_rejected", {"reason": "no-fresh-agent-output", "task_id": task.task_id})
            raise ValueError(message)
        preflight = self.writeback.validate_outputs(
            task,
            sandbox,
            runtime_id=str(run.get("runtime") or "opencode"),
        )
        if not preflight.passed:
            update_run_manifest(
                sandbox.manifest_path,
                recovery={"status": "rejected", "preflight": preflight.as_dict()},
            )
            self.observer.emit("run.resume_rejected", preflight.as_dict())
            raise ValueError("existing sandbox is not safe to resume: " + "; ".join(item.message for item in preflight.issues[:5]))

        update_run_manifest(
            sandbox.manifest_path,
            status="recovery_preflight_passed",
            recovery={"status": "accepted", "fresh_outputs": list(changed_outputs), "preflight": preflight.as_dict()},
        )
        self.observer.emit("validation.passed", {"kind": "recovery-preflight", **preflight.as_dict()})
        return self.writeback.complete_outputs(
            task,
            sandbox,
            str(run.get("runtime") or "opencode"),
        )
