"""Formal Agent Worker bound to the Literary Engineering CLI state machine."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any
from collections.abc import Callable

from ..application.config import load_config
from ..contracts import TaskPackage, load_task_package
from ..core_bridge import CoreBridge
from ..orchestration.active_plan import ActivePlanLoader, ActiveScenePlan
from ..orchestration.chapter_facts_io import load_production_chapter_policy
from ..orchestration.project_fingerprint import planning_project_fingerprint
from ..orchestration.scene_binding import bind_scene_task
from ..orchestration.settings import OrchestrationMode, orchestration_settings
from ..persistence.job_store import JobStore
from ..runtimes import build_runtime
from .bundle_executor import dispatch_serial_bundle
from .prepared_context_cache import PreparedContextCache
from .sandbox import (
    SandboxManifest,
    changed_agent_outputs,
    sandbox_from_run,
    update_run_manifest,
)
from .run_manifest import load_run
from .task_snapshot import load_run_task_snapshot
from .task_roles import runtime_role_for_task
from .worker_observability import WorkerObserver
from .worker_execution_profile import activate_execution_profile, build_runtime_kwargs
from .worker_paths import (
    resolve_task_json_path as _resolve_task_json_path,
    validate_project as _validate_project,
)
from .worker_results import WorkerRunResult, runtime_failure_fields
from .worker_preparation import prepare_worker_task
from .worker_writeback import WritebackCoordinator


class AgentWorker:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
        runtime_pool=None,
        plan_store=None,
        prepared_context_cache: PreparedContextCache | None = None,
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
        self.prepared_context_cache = prepared_context_cache
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
        return prepare_worker_task(
            project_root,
            route=route,
            runtime_id=runtime_id,
            task_id=task_id,
            scene=scene,
            config=self.config,
            bridge=self.bridge,
            observer=self.observer,
            select_task=self._select_task_package,
            prepared_context_cache=self.prepared_context_cache,
        )

    def _select_task_package(
        self,
        project: Path,
        *,
        route: str,
        task_id: str = "",
        scene: str = "",
        emit_binding_events: bool,
    ) -> tuple[TaskPackage | None, str]:
        selected_task_id = task_id.strip()
        if not selected_task_id:
            issued = self.bridge.task_next(project, route, scene=scene)
            if issued.fields.get("status") == "ready" or not issued.fields.get("task_id"):
                return None, str(
                    issued.fields.get("message") or "route has no pending task"
                )
            selected_task_id = str(issued.fields["task_id"])
        opened = self.bridge.task_open(project, selected_task_id)
        task_json_path = _resolve_task_json_path(
            project,
            selected_task_id,
            opened.fields.get("task_json", ""),
        )
        task = load_task_package(project, task_json_path)
        return (
            self._bind_active_scene_plan(task, emit_events=emit_binding_events),
            "",
        )

    def _active_scene_plan(self, project_root: Path) -> ActiveScenePlan | None:
        store = self.plan_store
        if store is None:
            application = self.config.get("application")
            payload = application if isinstance(application, dict) else {}
            store = JobStore(Path(str(payload.get("database_path") or "studio.sqlite3")))
        return ActivePlanLoader(
            store,
            fingerprint_provider=self.orchestration_fingerprint_provider,
        ).load(project_root)

    def _bind_active_scene_plan(
        self,
        task: TaskPackage,
        *,
        emit_events: bool = True,
    ) -> TaskPackage:
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
        try:
            active = self._active_scene_plan(task.project_root)
            if active is None:
                if emit_events:
                    self.observer.emit(
                        "orchestration.fixed_fallback",
                        {"task_id": task.task_id, "reason": "no-active-plan"},
                    )
                return task
            chapter_policy = None
            chapter_policy_digest = ""
            if settings.production_chapter_horizon:
                chapter_id = str(task.payload.get("chapter_id") or "").strip()
                scene_id = str(task.payload.get("scene_id") or "").strip()
                if not chapter_id:
                    raise ValueError(
                        "production chapter horizon requires task chapter_id"
                    )
                chapter_policy, chapter_policy_digest = (
                    load_production_chapter_policy(
                        task.project_root,
                        chapter_id,
                        active_scene_id=scene_id,
                        horizon_size=settings.chapter_horizon_size,
                    )
                )
            binding = bind_scene_task(
                task,
                plan=active.plan,
                graph=active.graph,
                current_project_fingerprint=active.project_fingerprint,
                chapter_policy=chapter_policy,
                chapter_policy_digest=chapter_policy_digest,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            if emit_events:
                self.observer.emit(
                    "orchestration.fixed_fallback",
                    {"task_id": task.task_id, "reason": str(exc)},
                )
            return task
        if emit_events:
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
        bundled = self._try_bundle_dispatch(
            project_root,
            route=route,
            runtime_id=runtime_id,
            task_id=task_id,
            scene=scene,
        )
        if bundled is not None:
            return bundled
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
        return self._run_prepared_task(task, sandbox, runtime_id=runtime_id)

    def _try_bundle_dispatch(
        self,
        project_root: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str,
        scene: str,
    ) -> WorkerRunResult | None:
        settings = orchestration_settings(self.config)
        enabled = (
            not task_id.strip()
            and route == "scene-development"
            and settings.bundle_execution
            and settings.effective_mode
            not in {OrchestrationMode.FIXED, OrchestrationMode.SHADOW}
        )
        if not enabled:
            return None
        return dispatch_serial_bundle(
            self,
            project_root,
            route=route,
            runtime_id=runtime_id,
            scene=scene,
        )

    def _run_prepared_task(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        *,
        runtime_id: str,
    ) -> WorkerRunResult:
        active_runtime = "deterministic-engine" if task.execution_contract.execution_policy == "deterministic" else runtime_id
        if task.execution_contract.execution_policy == "deterministic":
            return self._complete_deterministic_task(task, sandbox, active_runtime)
        if self.cancel_event.is_set():
            return self._cancelled_result(task, sandbox, runtime_id, "before-runner")
        runtime_result = self._execute_agent_runtime(task, sandbox, runtime_id)
        terminal = self._runtime_terminal_result(
            task,
            sandbox,
            runtime_id,
            runtime_result,
        )
        if terminal is not None:
            return terminal
        if self.cancel_event.is_set():
            return self._cancelled_result(task, sandbox, runtime_id, "before-writeback")
        return self.writeback.complete_outputs(task, sandbox, runtime_id)

    def _complete_deterministic_task(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        active_runtime: str,
    ) -> WorkerRunResult:
        self.observer.emit(
            "runner.skipped",
            {"reason": "deterministic-cli", "task_id": task.task_id},
        )
        update_run_manifest(
            sandbox.manifest_path,
            status="deterministic_outputs_ready",
            runtime_message="core deterministic command completed in the isolated workspace",
            runtime_returncode=0,
        )
        return self.writeback.complete_outputs(task, sandbox, active_runtime)

    def _execute_agent_runtime(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
    ):
        runtime = build_runtime(
            runtime_id,
            self.config,
            runtime_pool=self.runtime_pool,
            role=runtime_role_for_task(task),
        )
        worker_config = self.config.get("worker", {})
        profile, timeout = activate_execution_profile(
            task,
            sandbox,
            worker_config=worker_config,
            runtime_id=runtime_id,
            runtime=runtime,
            observer=self.observer,
        )
        self.observer.emit("runner.started", {"runner_id": runtime_id, "task_id": task.task_id})
        runtime_kwargs = build_runtime_kwargs(
            task,
            sandbox,
            runtime_id=runtime_id,
            timeout=timeout,
            profile=profile,
            worker_config=worker_config,
            observer=self.observer,
            cancel_event=self.cancel_event,
            writeback=self.writeback,
        )
        result = runtime.execute(
            sandbox.workspace,
            sandbox.prompt_path,
            sandbox.run_root,
            **runtime_kwargs,
        )
        self.observer.emit(
            "runner.completed",
            {
                "runner_id": runtime_id,
                "status": result.status,
                "returncode": result.returncode,
            },
        )
        update_run_manifest(
            sandbox.manifest_path,
            status=result.status,
            runtime_message=result.message,
            runtime_returncode=result.returncode,
            runtime_output=str(result.output_path) if result.output_path else "",
            runtime_metadata=result.metadata or {},
        )
        return result

    def _runtime_terminal_result(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
        runtime_result,
    ) -> WorkerRunResult | None:
        if runtime_result.status == "completed":
            return None
        status = runtime_result.status if runtime_result.status == "waiting_host_agent" else "runtime_failed"
        return WorkerRunResult(
            status,
            task.project_root,
            task.route,
            task.task_id,
            runtime_id,
            sandbox.run_root,
            sandbox.workspace,
            runtime_result.message,
            **runtime_failure_fields(runtime_result),
        )

    def _cancelled_result(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
        stage: str,
    ) -> WorkerRunResult:
        self.observer.emit("run.cancelled", {"stage": stage})
        message = (
            "run cancelled before Agent Runner execution"
            if stage == "before-runner"
            else "run cancelled before formal writeback"
        )
        return WorkerRunResult(
            "cancelled",
            task.project_root,
            task.route,
            task.task_id,
            runtime_id,
            sandbox.run_root,
            sandbox.workspace,
            message,
        )

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
