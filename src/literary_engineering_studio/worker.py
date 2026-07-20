"""Formal Agent Worker bound to the Literary Engineering CLI state machine."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .config import load_config
from .contracts import TaskPackage, load_task_package
from .core_bridge import CoreBridge
from .runtimes import build_runtime
from .sandbox import SandboxManifest, import_expected_outputs, stage_task, update_run_manifest


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
        }


class AgentWorker:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or load_config()
        self.bridge = CoreBridge(self.config)

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
                )
            selected_task_id = issued.fields["task_id"]

        opened = self.bridge.task_open(project, selected_task_id)
        task_json_value = opened.fields.get("task_json")
        if not task_json_value:
            raise RuntimeError("task-open did not report task_json")
        task = load_task_package(project, Path(task_json_value))
        if task.human_gate_reasons:
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

        command_error = ""
        if task.command and bool(self.config.get("worker", {}).get("auto_run_task_command", True)):
            try:
                self.bridge.execute_task_command(task.command, project)
            except (RuntimeError, ValueError, FileNotFoundError) as exc:
                command_error = str(exc)

        runs_root = Path(str(self.config.get("worker", {}).get("runs_root") or ""))
        sandbox = stage_task(task, runs_root, runtime=runtime_id)
        if command_error:
            update_run_manifest(
                sandbox.manifest_path,
                status="prepared_with_core_command_error",
                core_command_error=command_error,
            )
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

        runtime = build_runtime(runtime_id, self.config)
        timeout = int(self.config.get("worker", {}).get("timeout_seconds") or 1800)
        runtime_result = runtime.execute(sandbox.workspace, sandbox.prompt_path, sandbox.run_root, timeout=timeout)
        update_run_manifest(
            sandbox.manifest_path,
            status=runtime_result.status,
            runtime_message=runtime_result.message,
            runtime_returncode=runtime_result.returncode,
            runtime_output=str(runtime_result.output_path) if runtime_result.output_path else "",
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

        imported = import_expected_outputs(task, sandbox)
        if not imported:
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
            update_run_manifest(sandbox.manifest_path, status="blocked_by_core_gate", core_gate_error=str(exc))
            return WorkerRunResult(
                "blocked_by_core_gate",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                str(exc),
                imported,
            )

        audit = self.bridge.route_audit(task.project_root, task.route)
        update_run_manifest(
            sandbox.manifest_path,
            status="complete",
            imported_outputs=list(imported),
            route_audit=audit.fields,
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
            audit.fields,
        )


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

