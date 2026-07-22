"""Formal Agent Worker bound to the Literary Engineering CLI state machine."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Any
from collections.abc import Callable

from .config import load_config
from .contracts import TaskPackage, load_task_package
from .core_bridge import CoreBridge, task_command_parameters
from .runtimes import build_runtime
from .sandbox import (
    SandboxManifest,
    apply_expected_outputs,
    capture_core_managed_outputs,
    inspect_expected_outputs,
    load_writeback_preview,
    rollback_expected_outputs,
    restore_core_managed_outputs,
    sandbox_from_run,
    stage_task,
    update_run_manifest,
)
from .task_preflight import canonicalize_task_outputs, validate_task_outputs


@dataclass(frozen=True)
class WorkerRunResult:
    status: str
    project_root: Path
    route: str
    task_id: str
    runtime: str
    run_root: Path | None
    workspace: Path | None
    message: str
    imported_outputs: tuple[str, ...] = ()
    audit_fields: dict[str, str] | None = None
    writeback_preview: dict[str, object] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": str(self.project_root),
            "route": self.route,
            "task_id": self.task_id,
            "runtime": self.runtime,
            "run_root": str(self.run_root) if self.run_root else "",
            "workspace": str(self.workspace) if self.workspace else "",
            "message": self.message,
            "imported_outputs": list(self.imported_outputs),
            "audit": self.audit_fields or {},
            "writeback_preview": self.writeback_preview or {},
        }


class AgentWorker:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
        runtime_pool=None,
    ):
        self.config = config or load_config()
        self.bridge = CoreBridge(self.config)
        self.event_sink = event_sink
        self.cancel_event = cancel_event or threading.Event()
        self.runtime_pool = runtime_pool

    def prepare(
        self,
        project_root: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str = "",
        scene: str = "",
    ) -> tuple[TaskPackage | None, SandboxManifest | None, WorkerRunResult | None]:
        project = _validate_project(project_root)
        self._emit("task.selecting", {"project_root": str(project), "route": route})
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
        task_json_value = opened.fields.get("task_json")
        if not task_json_value:
            raise RuntimeError("task-open did not report task_json")
        task = load_task_package(project, Path(task_json_value))
        self._emit(
            "task.opened",
            {
                "task_id": task.task_id,
                "route": task.route,
                "current_state": task.current_state,
                "execution_contract": task.execution_contract.as_dict(),
            },
        )
        if task.human_gate_reasons:
            self._emit("human.required", {"reasons": list(task.human_gate_reasons), "task_id": task.task_id})
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
        sandbox = stage_task(task, runs_root, runtime=active_runtime)
        self._emit(
            "sandbox.prepared",
            {
                "run_id": sandbox.run_id,
                "run_root": str(sandbox.run_root),
                "workspace": str(sandbox.workspace),
                "project_root": str(task.project_root),
                "runner_id": active_runtime,
                "task_id": task.task_id,
            },
        )
        if task.command:
            unresolved = task_command_parameters(task.command)
            if unresolved:
                message = "当前任务需要先确定：" + "、".join(unresolved)
                self._emit(
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
            self._emit("core.command_started", {"task_id": task.task_id})
            try:
                command_result = self.bridge.execute_task_command(task.command, sandbox.workspace)
            except (RuntimeError, ValueError, FileNotFoundError) as exc:
                update_run_manifest(
                    sandbox.manifest_path,
                    status="core_command_failed",
                    core_command_error=str(exc),
                )
                self._emit("core.command_failed", {"task_id": task.task_id, "error": str(exc)})
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
                self._emit("core.outputs_protected", {"task_id": task.task_id, "paths": list(protected)})
            self._emit("core.command_completed", {"task_id": task.task_id, "returncode": command_result.returncode})
        return task, sandbox, None

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
            self._emit("runner.skipped", {"reason": "deterministic-cli", "task_id": task.task_id})
            update_run_manifest(
                sandbox.manifest_path,
                status="deterministic_outputs_ready",
                runtime_message="core deterministic command completed in the isolated workspace",
                runtime_returncode=0,
            )
            return self._complete_outputs(task, sandbox, active_runtime)

        if self.cancel_event.is_set():
            self._emit("run.cancelled", {"stage": "before-runner"})
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
        self._emit("runner.started", {"runner_id": runtime_id, "task_id": task.task_id})
        runtime_kwargs = {
            "timeout": timeout,
            "event_sink": self._emit,
            "cancel_event": self.cancel_event,
        }
        if runtime_id == "opencode":
            def validate_outputs():
                restored = restore_core_managed_outputs(sandbox)
                if restored:
                    self._emit("core.outputs_restored", {"task_id": task.task_id, "paths": list(restored)})
                normalized = canonicalize_task_outputs(task, sandbox)
                if normalized:
                    self._emit("validation.canonicalized", {"changes": normalized})
                return validate_task_outputs(task, sandbox)

            runtime_kwargs.update(
                {
                    "output_validator": validate_outputs,
                    "max_repairs": int(self.config.get("worker", {}).get("max_repair_attempts") or 2),
                }
            )
        runtime_result = runtime.execute(
            sandbox.workspace,
            sandbox.prompt_path,
            sandbox.run_root,
            **runtime_kwargs,
        )
        self._emit(
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
            self._emit("run.cancelled", {"stage": "before-writeback"})
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

        return self._complete_outputs(task, sandbox, runtime_id)

    def _complete_outputs(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
    ) -> WorkerRunResult:
        if not task.expected_outputs:
            update_run_manifest(
                sandbox.manifest_path,
                status="blocked_empty_submission",
                message="task has no expected_outputs; human evidence selection is required",
            )
            return WorkerRunResult(
                "waiting_human",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                "task has no expected_outputs; choose formal submission evidence manually",
            )

        self._emit("validation.started", {"kind": "expected-output-preview"})
        preview = inspect_expected_outputs(task, sandbox)
        self._emit("writeback.preview_ready", preview.as_dict())
        if preview.policy != "automatic":
            update_run_manifest(
                sandbox.manifest_path,
                status="awaiting_writeback_approval",
                writeback_preview=preview.as_dict(),
            )
            return WorkerRunResult(
                "waiting_writeback",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                "Agent output is ready; review the writeback diff before importing it",
                writeback_preview=preview.as_dict(),
            )
        return self._finalize(task, sandbox, preview, approved_by="policy:automatic")

    def approve_writeback(self, run_root: Path, *, approved_by: str) -> WorkerRunResult:
        run = load_run(run_root)
        if str(run.get("status") or "") != "awaiting_writeback_approval":
            raise ValueError("run is not awaiting writeback approval")
        project = _validate_project(Path(str(run.get("project_root") or "")))
        task_json = Path(str(run.get("task_json") or ""))
        if not task_json.is_file():
            task_json = project / "workflow" / "tasks" / f"{run.get('task_id')}.json"
        task = load_task_package(project, task_json)
        sandbox = sandbox_from_run(run_root)
        preview = load_writeback_preview(run_root)
        if preview.policy not in {"preview-required", "approval-required"}:
            raise ValueError(f"writeback does not require approval: {preview.policy}")
        update_run_manifest(
            sandbox.manifest_path,
            writeback_decision={
                "decision": "approve",
                "approved_by": approved_by.strip() or "studio-user",
            },
        )
        self._emit("writeback.approved", {"approved_by": approved_by.strip() or "studio-user"})
        return self._finalize(task, sandbox, preview, approved_by=approved_by)

    def resume_from_run(self, run_root: Path) -> WorkerRunResult:
        """Resume only when an existing sandbox is already complete and valid."""
        run = load_run(run_root)
        project = _validate_project(Path(str(run.get("project_root") or "")))
        task_json = Path(str(run.get("task_json") or ""))
        if not task_json.is_file():
            task_json = project / "workflow" / "tasks" / f"{run.get('task_id')}.json"
        task = load_task_package(project, task_json)
        sandbox = sandbox_from_run(run_root)
        if str(run.get("task_id") or "") != task.task_id:
            raise ValueError("recovery sandbox task identity does not match its task package")

        self._emit("run.resume_started", {"run_root": str(sandbox.run_root), "task_id": task.task_id})
        restored = restore_core_managed_outputs(sandbox)
        if restored:
            self._emit("core.outputs_restored", {"task_id": task.task_id, "paths": list(restored), "recovery": True})
        normalized = canonicalize_task_outputs(task, sandbox)
        if normalized:
            self._emit("validation.canonicalized", {"changes": normalized, "recovery": True})
        preflight = validate_task_outputs(task, sandbox)
        if not preflight.passed:
            update_run_manifest(
                sandbox.manifest_path,
                recovery={"status": "rejected", "preflight": preflight.as_dict()},
            )
            self._emit("run.resume_rejected", preflight.as_dict())
            raise ValueError("existing sandbox is not safe to resume: " + "; ".join(item.message for item in preflight.issues[:5]))

        update_run_manifest(
            sandbox.manifest_path,
            status="recovery_preflight_passed",
            recovery={"status": "accepted", "preflight": preflight.as_dict()},
        )
        self._emit("validation.passed", {"kind": "recovery-preflight", **preflight.as_dict()})
        return self._complete_outputs(task, sandbox, str(run.get("runtime") or "opencode"))

    def reject_writeback(self, run_root: Path, *, rejected_by: str, reason: str = "") -> WorkerRunResult:
        run = load_run(run_root)
        if str(run.get("status") or "") != "awaiting_writeback_approval":
            raise ValueError("run is not awaiting writeback approval")
        sandbox = sandbox_from_run(run_root)
        update_run_manifest(
            sandbox.manifest_path,
            status="writeback_rejected",
            writeback_decision={
                "decision": "reject",
                "rejected_by": rejected_by.strip() or "studio-user",
                "reason": reason.strip(),
            },
        )
        self._emit("writeback.rejected", {"reason": reason.strip()})
        return WorkerRunResult(
            "writeback_rejected",
            Path(str(run["project_root"])),
            str(run.get("route") or ""),
            str(run.get("task_id") or ""),
            str(run.get("runtime") or ""),
            sandbox.run_root,
            sandbox.workspace,
            reason.strip() or "writeback rejected by user",
            writeback_preview=load_writeback_preview(run_root).as_dict(),
        )

    def _finalize(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        preview,
        *,
        approved_by: str,
    ) -> WorkerRunResult:
        runtime_id = str(load_run(sandbox.run_root).get("runtime") or "opencode")
        imported = apply_expected_outputs(task, sandbox, preview)
        self._emit("file.imported", {"paths": list(imported), "approved_by": approved_by})
        self.bridge.task_submit(
            task.project_root,
            task.task_id,
            imported,
            note=f"executed by literary-engineering-studio runtime={runtime_id}",
        )
        try:
            self.bridge.task_complete(
                task.project_root,
                task.task_id,
                handled_by=f"studio:{runtime_id}",
            )
        except (RuntimeError, ValueError, FileNotFoundError) as exc:
            self._emit("validation.blocked", {"kind": "core-task-gate", "error": str(exc)})
            rollback_expected_outputs(task, sandbox, imported)
            update_run_manifest(
                sandbox.manifest_path,
                status="blocked_by_core_gate",
                core_gate_error=str(exc),
                imported_outputs=[],
            )
            return WorkerRunResult(
                "blocked_by_core_gate",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                str(exc),
                (),
                writeback_preview=preview.as_dict(),
            )

        audit_fields = {
            "status": "pass",
            "scope": "exact-task-gate",
            "route": task.route,
            "task_id": task.task_id,
        }
        self._emit("validation.passed", {"kind": "exact-task-gate", "audit": audit_fields})
        update_run_manifest(
            sandbox.manifest_path,
            status="complete",
            imported_outputs=list(imported),
            route_audit=audit_fields,
        )
        return WorkerRunResult(
            "complete",
            task.project_root,
            task.route,
            task.task_id,
            runtime_id,
            sandbox.run_root,
            sandbox.workspace,
            "Agent output imported and accepted by the core task gate",
            imported,
            audit_fields,
            preview.as_dict(),
        )

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_sink is not None:
            self.event_sink(event, data)


def load_run(run_root: Path) -> dict[str, Any]:
    path = run_root.resolve() / "run.json"
    if not path.exists():
        raise FileNotFoundError(f"Studio run not found: {run_root}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid Studio run manifest: {path}")
    return payload


def _validate_project(value: Path) -> Path:
    project = value.expanduser().resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"work project not found: {project}")
    if not (project / "project.yaml").exists():
        raise ValueError(f"not a Literary Engineering work project: {project}")
    return project
