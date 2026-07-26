"""Deterministic preflight, preview, writeback, rollback, and receipt lifecycle."""

from __future__ import annotations

from pathlib import Path

from ..contracts import TaskPackage, load_task_package
from ..task_preflight import canonicalize_task_outputs, validate_task_outputs
from .mutation_tracking import WorkerMutationTracker
from .run_manifest import load_run
from .sandbox import (
    SandboxManifest,
    apply_expected_outputs,
    control_sandbox_view,
    inspect_expected_outputs,
    load_writeback_preview,
    rollback_expected_outputs,
    sandbox_from_run,
    sync_agent_outputs_to_control,
    restore_core_managed_outputs,
    update_run_manifest,
)
from .worker_paths import resolve_task_json_path, validate_project
from .worker_results import WorkerRunResult


class WorkerWritebackMixin:
    """Requires ``bridge``, ``_emit``, and ``_agent_session_id`` from AgentWorker."""

    def _complete_outputs(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
    ) -> WorkerRunResult:
        if not task.expected_outputs:
            return self._empty_submission(task, sandbox, runtime_id)
        preflight = self._validate_outputs(task, sandbox, runtime_id=runtime_id)
        if not preflight.passed:
            update_run_manifest(
                sandbox.manifest_path,
                status="preflight_failed",
                preflight=preflight.as_dict(),
            )
            return WorkerRunResult(
                "preflight_failed",
                task.project_root,
                task.route,
                task.task_id,
                runtime_id,
                sandbox.run_root,
                sandbox.workspace,
                "; ".join(item.message for item in preflight.issues[:5]),
            )

        self._emit("validation.started", {"kind": "expected-output-preview"})
        preview = inspect_expected_outputs(task, sandbox)
        self._mutation_tracker(task, sandbox, runtime_id).previewed(preview)
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

    def approve_writeback(
        self,
        run_root: Path,
        *,
        approved_by: str,
    ) -> WorkerRunResult:
        run, task, sandbox = self._writeback_context(run_root)
        if str(run.get("status") or "") != "awaiting_writeback_approval":
            raise ValueError("run is not awaiting writeback approval")
        preview = load_writeback_preview(run_root)
        if preview.policy not in {"preview-required", "approval-required"}:
            raise ValueError(f"writeback does not require approval: {preview.policy}")
        actor = approved_by.strip() or "studio-user"
        update_run_manifest(
            sandbox.manifest_path,
            writeback_decision={"decision": "approve", "approved_by": actor},
        )
        self._emit("writeback.approved", {"approved_by": actor})
        return self._finalize(task, sandbox, preview, approved_by=actor)

    def reject_writeback(
        self,
        run_root: Path,
        *,
        rejected_by: str,
        reason: str = "",
    ) -> WorkerRunResult:
        run, task, sandbox = self._writeback_context(run_root)
        if str(run.get("status") or "") != "awaiting_writeback_approval":
            raise ValueError("run is not awaiting writeback approval")
        actor = rejected_by.strip() or "studio-user"
        update_run_manifest(
            sandbox.manifest_path,
            status="writeback_rejected",
            writeback_decision={
                "decision": "reject",
                "rejected_by": actor,
                "reason": reason.strip(),
            },
        )
        preview = load_writeback_preview(run_root)
        self._mutation_tracker(
            task,
            sandbox,
            str(run.get("runtime") or ""),
        ).rejected(preview)
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
            writeback_preview=preview.as_dict(),
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
        mutations = self._mutation_tracker(task, sandbox, runtime_id)
        imported = apply_expected_outputs(task, sandbox, preview)
        mutations.applied(preview)
        self._emit(
            "file.imported",
            {"paths": list(imported), "approved_by": approved_by},
        )
        try:
            self.bridge.task_submit(
                task.project_root,
                task.task_id,
                imported,
                note=f"executed by literary-engineering-studio runtime={runtime_id}",
            )
            self.bridge.task_complete(
                task.project_root,
                task.task_id,
                handled_by=f"studio:{runtime_id}",
            )
        except (RuntimeError, ValueError, FileNotFoundError) as exc:
            return self._rollback_core_gate(
                task,
                sandbox,
                preview,
                imported,
                runtime_id,
                mutations,
                exc,
            )
        return self._complete_core_gate(
            task,
            sandbox,
            preview,
            imported,
            runtime_id,
            mutations,
        )

    def _rollback_core_gate(
        self,
        task,
        sandbox,
        preview,
        imported,
        runtime_id,
        mutations,
        error,
    ) -> WorkerRunResult:
        self._emit(
            "validation.blocked",
            {"kind": "core-task-gate", "error": str(error)},
        )
        rollback_expected_outputs(task, sandbox, imported)
        mutations.rolled_back(preview)
        rollback_error = ""
        try:
            self.bridge.task_revert_submission(
                task.project_root,
                task.task_id,
                reason=(
                    "Studio worker rolled back imported outputs after core gate "
                    f"failure: {error}"
                ),
            )
        except (RuntimeError, ValueError, FileNotFoundError) as exc:
            rollback_error = str(exc)
        update_run_manifest(
            sandbox.manifest_path,
            status="blocked_by_core_gate",
            core_gate_error=str(error),
            imported_outputs=[],
            core_submission_rollback="pass" if not rollback_error else rollback_error,
        )
        return WorkerRunResult(
            "blocked_by_core_gate",
            task.project_root,
            task.route,
            task.task_id,
            runtime_id,
            sandbox.run_root,
            sandbox.workspace,
            str(error),
            (),
            writeback_preview=preview.as_dict(),
        )

    def _complete_core_gate(
        self,
        task,
        sandbox,
        preview,
        imported,
        runtime_id,
        mutations,
    ) -> WorkerRunResult:
        audit = {
            "status": "pass",
            "scope": "exact-task-gate",
            "route": task.route,
            "task_id": task.task_id,
        }
        self._emit("validation.passed", {"kind": "exact-task-gate", "audit": audit})
        mutations.promoted(preview)
        update_run_manifest(
            sandbox.manifest_path,
            status="complete",
            imported_outputs=list(imported),
            route_audit=audit,
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
            audit,
            preview.as_dict(),
        )

    def _validate_outputs(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        *,
        runtime_id: str,
    ):
        restored = restore_core_managed_outputs(sandbox)
        if restored:
            self._emit(
                "core.outputs_restored",
                {"task_id": task.task_id, "paths": list(restored)},
            )
        normalized = canonicalize_task_outputs(task, sandbox)
        if normalized:
            self._emit("validation.canonicalized", {"changes": normalized})
        synced = sync_agent_outputs_to_control(task, sandbox)
        if synced:
            self._emit(
                "agent.outputs_staged",
                {"task_id": task.task_id, "paths": list(synced)},
            )
        result = validate_task_outputs(task, control_sandbox_view(sandbox))
        tracker = self._mutation_tracker(task, sandbox, runtime_id)
        tracker.candidate_outputs(
            preflight_status="pass" if result.passed else "rejected"
        )
        if not result.passed:
            tracker.preflight_rejected()
        return result

    def _mutation_tracker(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        runtime_id: str,
    ) -> WorkerMutationTracker:
        run = load_run(sandbox.run_root)
        session_id = (
            self._agent_session_id
            or str(run.get("mutation_session_id") or "")
            or _fallback_session(runtime_id, sandbox.run_id)
        )
        if str(run.get("mutation_session_id") or "") != session_id:
            update_run_manifest(sandbox.manifest_path, mutation_session_id=session_id)
        return WorkerMutationTracker(
            task,
            sandbox,
            session_id=session_id,
            event_sink=self._emit,
        )

    @staticmethod
    def _empty_submission(task, sandbox, runtime_id) -> WorkerRunResult:
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

    @staticmethod
    def _writeback_context(run_root: Path):
        run = load_run(run_root)
        project = validate_project(Path(str(run.get("project_root") or "")))
        task_json = Path(str(run.get("task_json") or ""))
        if not task_json.is_file():
            task_json = resolve_task_json_path(
                project,
                str(run.get("task_id") or ""),
                str(task_json),
            )
        return run, load_task_package(project, task_json), sandbox_from_run(run_root)


def _fallback_session(runtime_id: str, run_id: str) -> str:
    return (
        f"deterministic:{run_id}"
        if runtime_id == "deterministic-engine"
        else f"worker-run:{run_id}"
    )
