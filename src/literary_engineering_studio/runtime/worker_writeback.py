"""Deterministic preflight, preview, writeback, rollback, and receipt lifecycle."""

from __future__ import annotations

from pathlib import Path

from ..contracts import TaskPackage
from ..preflight.common import PreflightIssue, PreflightResult
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
    sandbox_change_issues,
    sync_agent_outputs_to_control,
    restore_core_managed_outputs,
    update_run_manifest,
)
from .sandbox_hygiene import restore_unexpected_agent_changes
from .worker_paths import validate_project
from .task_snapshot import load_run_task_snapshot
from .worker_results import WorkerRunResult


class WorkerWritebackMixin:
    """Requires ``bridge`` and an explicit ``observer`` from AgentWorker."""

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

        self.observer.emit("validation.started", {"kind": "expected-output-preview"})
        preview = inspect_expected_outputs(task, sandbox)
        self._mutation_tracker(task, sandbox, runtime_id).previewed(preview)
        self.observer.emit("writeback.preview_ready", preview.as_dict())
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
                "候选成果已通过预检，正式项目尚未改变。请查看写回差异后确认导入或退回。",
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
        self.observer.emit("writeback.approved", {"approved_by": actor})
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
        self.observer.emit("writeback.rejected", {"reason": reason.strip()})
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
        self.observer.emit(
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
        self.observer.emit(
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
        self.observer.emit("validation.passed", {"kind": "exact-task-gate", "audit": audit})
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
        restored_unexpected = restore_unexpected_agent_changes(sandbox)
        if restored_unexpected:
            self.observer.emit(
                "sandbox.unexpected_changes_restored",
                {
                    "task_id": task.task_id,
                    "count": len(restored_unexpected),
                    "paths": list(restored_unexpected),
                },
            )
        restored = restore_core_managed_outputs(sandbox)
        if restored:
            self.observer.emit(
                "core.outputs_restored",
                {"task_id": task.task_id, "paths": list(restored)},
            )
        normalized = canonicalize_task_outputs(task, sandbox)
        if normalized:
            self.observer.emit("validation.canonicalized", {"changes": normalized})
        synced = sync_agent_outputs_to_control(task, sandbox)
        if synced:
            self.observer.emit(
                "agent.outputs_staged",
                {"task_id": task.task_id, "paths": list(synced)},
            )
        result = validate_task_outputs(task, control_sandbox_view(sandbox))
        remaining_changes = sandbox_change_issues(sandbox)
        if remaining_changes:
            result = PreflightResult(
                False,
                (
                    *(
                        PreflightIssue(
                            "unexpected-change",
                            "workspace",
                            message,
                            (
                                "Studio 无法从受控基线恢复该路径；"
                                "停止本次运行并重新创建沙箱。"
                            ),
                        )
                        for message in remaining_changes
                    ),
                    *result.issues,
                ),
            )
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
            self.observer.agent_session_id
            or str(run.get("mutation_session_id") or "")
            or _fallback_session(runtime_id, sandbox.run_id)
        )
        if str(run.get("mutation_session_id") or "") != session_id:
            update_run_manifest(sandbox.manifest_path, mutation_session_id=session_id)
        return WorkerMutationTracker(
            task,
            sandbox,
            session_id=session_id,
            event_sink=self.observer.emit,
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
        task = load_run_task_snapshot(
            run_root,
            project_root=project,
            manifest=run,
        )
        return run, task, sandbox_from_run(run_root)


def _fallback_session(runtime_id: str, run_id: str) -> str:
    return (
        f"deterministic:{run_id}"
        if runtime_id == "deterministic-engine"
        else f"worker-run:{run_id}"
    )
