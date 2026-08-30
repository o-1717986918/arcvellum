"""Result, recovery, and progress handling for one claimed Autopilot loop."""

from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any, Callable

from ..advisor.creative_steward import CreativeSteward
from ..orchestration import RecoveryDecision, RecoveryStep, recovery_step
from ..runtime.worker import WorkerRunResult
from .campaign_runtime import CampaignRuntimeCoordinator, FormalProgressEvidence
from .policy import DelegationPolicy, next_revision_count
from .route_dependencies import dependency_label, dependency_pending
from .run_result_contracts import RouteCycle, RunLoopHost
from .support import _now, _operational_decision, _project_progress_fingerprint, _repeated_completion_result
_TRANSPORT_FAILURE_KINDS = frozenset({"transient_network", "first_event_timeout", "idle_timeout"})
class ClaimedRunResultHandler:
    """Handle one Worker result without owning the run loop or persistence."""

    def __init__(
        self,
        host: RunLoopHost,
        *,
        run_id: str,
        project: Path,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        stop: threading.Event,
        dependency_probe: Callable[[Path], bool],
        repair_probe: Callable[[Path], bool] | None = None,
        scene_probe: Callable[[Path], bool] | None = None,
        campaign: CampaignRuntimeCoordinator | None,
    ) -> None:
        self.host = host
        self.run_id = run_id
        self.project = project
        self.policy = policy
        self.steward = steward
        self.stop = stop
        self.dependency_probe = dependency_probe
        self.repair_probe = repair_probe or (lambda _project: False)
        self.scene_probe = scene_probe or (lambda _project: False)
        self.campaign = campaign
        self.failure_by_task: dict[str, int] = {}
        self.transport_failure_by_task: dict[str, int] = {}
        self._recorded_recovery_decisions: set[tuple[str, str, int]] = set()

    def handle(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
        progress_before: str,
    ) -> bool:
        if result.status == "route_ready":
            return self._handle_route_ready(cycle, result)
        if result.status == "complete":
            return self._record_progress(
                run, cycle, result, progress_before, emit_event=True
            )
        if result.status == "waiting_writeback":
            final = self._approve_writeback(run, cycle, result)
            if final is None:
                return True
            if final.status == "complete":
                return self._record_progress(
                    run, cycle, final, progress_before, emit_event=False
                )
            result = final
        if result.status == "waiting_human":
            return self._handle_waiting_human(cycle, result)
        if result.status == "cancelled" or self.stop.is_set():
            return self._handle_cancelled()
        return self._handle_failure(cycle, result)

    def recover_runtime_failure(
        self,
        result: WorkerRunResult,
        cycle: RouteCycle,
    ) -> WorkerRunResult:
        if (
            result.status != "runtime_failed"
            or result.run_root is None
            or self.stop.is_set()
        ):
            return result
        failure_kind = result.failure_kind or "process_crash"
        if result.retryable is False or failure_kind not in {
            "process_crash",
            "validation_failure",
            "writeback_failure",
        }:
            return result
        task_key = result.task_id or f"{cycle.route}:unknown"
        attempt = self.failure_by_task.get(task_key, 0) + 1
        if not self._checkpoint_restore_allowed(task_key, attempt, failure_kind):
            return result
        self.host.runs.append_autopilot_event(
            self.run_id,
            "task.recovery_started",
            {"task_id": result.task_id, "run_root": str(result.run_root)},
        )
        coordinator = self.host.execution_coordinator
        if coordinator is not None and not coordinator.acquire(self.project, cycle.owner):
            return result
        try:
            recovered = self.host._worker(self.run_id).resume_from_run(result.run_root)
            self.host.runs.append_autopilot_event(
                self.run_id,
                "task.recovery_succeeded",
                {"task_id": recovered.task_id, "status": recovered.status},
            )
            return recovered
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            self.host.runs.append_autopilot_event(
                self.run_id,
                "task.recovery_rejected",
                {"task_id": result.task_id, "message": str(exc)},
            )
            return result
        finally:
            if coordinator is not None:
                coordinator.release(self.project, cycle.owner)

    def progress_identity(self) -> tuple[str, FormalProgressEvidence | None]:
        if self.campaign is None:
            return _project_progress_fingerprint(self.project), None
        evidence = self.campaign.progress_evidence()
        return evidence.progress.fingerprint, evidence

    def _checkpoint_restore_allowed(
        self, task_id: str, attempt: int, failure_kind: str = "process_crash"
    ) -> bool:
        if self.campaign is None:
            return True
        decision = self._recovery_decision(failure_kind, attempt, task_id)
        if decision.step is not RecoveryStep.CHECKPOINT_RESTORE:
            return False
        allowed, reason = self.campaign.restore_allowed()
        if not allowed:
            self.host.runs.append_autopilot_event(
                self.run_id,
                "task.recovery_rejected",
                {"task_id": task_id, "reason": reason, "attempt": attempt},
            )
        return allowed

    def _handle_route_ready(self, cycle: RouteCycle, result: WorkerRunResult) -> bool:
        if cycle.dependency_route:
            if dependency_pending(
                self.project,
                cycle,
                asset_probe=self.dependency_probe,
                length_repair_probe=self.repair_probe,
                scene_probe=self.scene_probe,
            ):
                return self.host._register_no_progress(
                    self.run_id,
                    result.task_id or f"{cycle.route}:dependency",
                    cycle.route,
                    f"依赖路线报告完成，但{dependency_label(cycle)}仍未解除。",
                )
            self.host.runs.append_autopilot_event(
                self.run_id,
                "route.dependency_ready",
                {
                    "route": cycle.route,
                    "resume_route": cycle.planned_route,
                    "dependency_kind": cycle.dependency_kind,
                },
            )
            self._reset_route_progress(
                cycle.resume_route_index
                if cycle.resume_route_index is not None
                else cycle.route_index
            )
            return False
        self.host.runs.append_autopilot_event(
            self.run_id, "route.ready", {"route": cycle.route}
        )
        self._reset_route_progress(cycle.route_index + 1)
        return False

    def _reset_route_progress(self, route_index: int) -> None:
        fingerprint, _ = self.progress_identity()
        self.host.runs.update_autopilot_run(
            self.run_id,
            route_index=route_index,
            current_task_id="",
            stalled_cycles=0,
            last_error="",
            progress_fingerprint=fingerprint,
            last_progress_at=_now(),
        )

    def _record_progress(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
        progress_before: str,
        *,
        emit_event: bool,
    ) -> bool:
        task_key = result.task_id or f"{cycle.route}:unknown"
        self.failure_by_task.pop(task_key, None)
        self.transport_failure_by_task.pop(task_key, None)
        repeated = _repeated_completion_result(self.host, run, self.run_id, result.task_id, cycle.route)
        if repeated is not None:
            return repeated
        progress_after, evidence = self.progress_identity()
        if progress_after == progress_before:
            return self._record_stall(cycle, result, emit_event)
        advanced = self.host.runs.advance_autopilot_run(
            self.run_id,
            consecutive_revisions=next_revision_count(run, result.task_id),
            failures=0,
            last_error="",
            progress_fingerprint=progress_after,
            stalled_cycles=0,
            last_progress_at=_now(),
        )
        self._commit_checkpoint(advanced, cycle, result, evidence)
        if emit_event:
            self.host.runs.append_autopilot_event(
                self.run_id,
                "progress.advanced",
                {
                    "route": cycle.route,
                    "task_id": result.task_id,
                    "fingerprint": progress_after,
                },
            )
        return False

    def _record_stall(
        self, cycle: RouteCycle, result: WorkerRunResult, emit_event: bool
    ) -> bool:
        suffix = "unknown" if emit_event else "writeback"
        message = (
            "任务报告完成，但项目正式状态没有发生可验证变化。"
            if emit_event
            else "写回报告完成，但正式项目没有出现新的可验证产物。"
        )
        return self.host._register_no_progress(
            self.run_id,
            result.task_id or f"{cycle.route}:{suffix}",
            cycle.route,
            message,
        )

    def _commit_checkpoint(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
        evidence: FormalProgressEvidence | None,
    ) -> None:
        if self.campaign is None or evidence is None:
            return
        checkpoint = self.campaign.checkpoint_after_progress(
            run,
            route=cycle.route,
            task_id=result.task_id,
            evidence=evidence,
            created_at=_now(),
        )
        if checkpoint is None:
            return
        self.host.runs.append_autopilot_event(
            self.run_id,
            "campaign.checkpoint.committed",
            {
                "checkpoint_sequence": checkpoint["sequence"],
                "task_id": result.task_id,
                "completed_steps": run["tasks_completed"],
            },
        )

    def _approve_writeback(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
    ) -> WorkerRunResult | None:
        if not self.policy.permits_writeback(cycle.route):
            self.host._pause_for(
                self.run_id, "writeback-approval-required", result.message
            )
            return None
        coordinator = self.host.execution_coordinator
        if coordinator is not None and not coordinator.acquire(self.project, cycle.owner):
            self.host._pause_for(
                self.run_id,
                "project-busy",
                "正式写回前发现另一项任务正在使用作品，请稍后继续。",
            )
            return None
        try:
            final = self.host._worker(self.run_id).approve_writeback(
                result.run_root,
                approved_by="delegated-agent:autopilot-controller",
            )
        finally:
            if coordinator is not None:
                coordinator.release(self.project, cycle.owner)
        self.host.runs.record_delegated_decision(
            self.run_id,
            _operational_decision(
                run,
                cycle.route,
                result.task_id,
                "writeback_approval",
                "approve",
                "授权策略允许导入已校验的预期产物。",
            ),
        )
        return final

    def _handle_waiting_human(
        self, cycle: RouteCycle, result: WorkerRunResult
    ) -> bool:
        choices = self.host._current_choices(self.project, cycle.route)
        choice = next(
            (
                item
                for item in choices
                if not result.task_id
                or not item.get("task_id")
                or item.get("task_id") == result.task_id
            ),
            None,
        )
        decision_type = str(choice.get("decision_type") or "") if choice else ""
        if not choice or not self.policy.permits(cycle.route, decision_type):
            self.host._pause_for(
                self.run_id, "human-decision-required", result.message
            )
            return True
        return not self.host._delegate_choice(
            self.run_id,
            self.project,
            cycle.route,
            self.policy,
            self.steward,
            choice,
            task_id=result.task_id,
            stop=self.stop,
        )

    def _handle_cancelled(self) -> bool:
        if getattr(self.stop, "_arcvellum_lease_lost", False):
            return True
        self.host._pause_for(self.run_id, "user-request", "自动创作已暂停。")
        return True

    def _handle_failure(self, cycle: RouteCycle, result: WorkerRunResult) -> bool:
        task_key = result.task_id or f"{cycle.route}:unknown"
        if (
            result.retryable is not False
            and result.failure_kind in _TRANSPORT_FAILURE_KINDS
        ):
            return self._handle_transport_failure(cycle, result, task_key)
        failure_count = self.failure_by_task.get(task_key, 0) + 1
        self.failure_by_task[task_key] = failure_count
        self.host.runs.update_autopilot_run(
            self.run_id, failures=failure_count, last_error=result.message
        )
        self.host.runs.append_autopilot_event(
            self.run_id,
            "task.failed",
            {
                "task_id": task_key,
                "status": result.status,
                "message": result.message,
                "failure_kind": result.failure_kind,
                "retryable": result.retryable,
            },
        )
        if result.retryable is False:
            pause_reason = {
                "provider_quota": "provider-billing-required",
                "authentication_failure": "model-authentication-required",
                "model_error": "model-connection-failed",
                "total_timeout": "task-runtime-limit-exceeded",
            }.get(result.failure_kind, "non-retryable-runtime-failure")
            self.host._pause_for(self.run_id, pause_reason, result.message)
            return True
        if self.campaign is not None:
            recovery_outcome = self._apply_recovery_step(
                cycle,
                task_key,
                failure_count,
                result.failure_kind or "process_crash",
            )
            if recovery_outcome is not None:
                return recovery_outcome
        limit = int(self.policy.payload["limits"]["max_failures_per_task"])
        if failure_count > limit:
            self.host._pause_for(
                self.run_id, "repeated-task-failure", result.message
            )
            return True
        time.sleep(min(5, failure_count))
        return False

    def _handle_transport_failure(
        self,
        cycle: RouteCycle,
        result: WorkerRunResult,
        task_key: str,
    ) -> bool:
        attempt = self.transport_failure_by_task.get(task_key, 0) + 1
        self.transport_failure_by_task[task_key] = attempt
        decision = self._recovery_decision(result.failure_kind, attempt, task_key)
        self.host.runs.update_autopilot_run(self.run_id, last_error=result.message)
        self.host.runs.append_autopilot_event(
            self.run_id,
            "task.transport_interrupted",
            {
                "task_id": task_key,
                "route": cycle.route,
                "failure_kind": result.failure_kind,
                "attempt": attempt,
                "recovery_step": decision.step.value,
                "literary_failure_count": self.failure_by_task.get(task_key, 0),
            },
        )
        if decision.step is RecoveryStep.STOP_WITH_EVIDENCE:
            self.host._pause_for(
                self.run_id,
                "model-connection-temporarily-unavailable",
                "模型连接连续返回空响应或中断。当前文学任务未被判定失败，"
                "系统已保留原任务与连接诊断，请稍后恢复自动创作。",
            )
            return True
        if decision.step is RecoveryStep.SESSION_RENEW:
            self.host.runs.append_autopilot_event(
                self.run_id,
                "runner.session.renew_requested",
                {"task_id": task_key, "route": cycle.route, "attempt": attempt},
            )
        delay = min(10, 2 ** (attempt - 1))
        self.host.runs.append_autopilot_event(
            self.run_id,
            "task.transport_retry_scheduled",
            {"task_id": task_key, "attempt": attempt, "delay_seconds": delay},
        )
        time.sleep(delay)
        return False

    def _apply_recovery_step(
        self,
        cycle: RouteCycle,
        task_id: str,
        attempt: int,
        failure_kind: str = "process_crash",
    ) -> bool | None:
        decision = self._recovery_decision(failure_kind, attempt, task_id)
        if decision.step is RecoveryStep.BOUNDED_REPLAN:
            self.host.runs.update_autopilot_run(
                self.run_id, current_task_id="", last_recovery_at=_now()
            )
            self.host.runs.append_autopilot_event(
                self.run_id,
                "campaign.replan.requested",
                {"task_id": task_id, "route": cycle.route, "reason": failure_kind},
            )
            return False
        if decision.step is RecoveryStep.STOP_WITH_EVIDENCE:
            self.host._pause_for(
                self.run_id,
                "recovery-exhausted",
                f"任务 {task_id} 的有界恢复已耗尽，系统已保留失败证据。",
            )
            return True
        return None

    def _recovery_decision(
        self, failure_code: str, attempt: int, task_id: str
    ) -> RecoveryDecision:
        decision = recovery_step(failure_code, attempt)
        identity = (task_id, failure_code, attempt)
        if identity not in self._recorded_recovery_decisions:
            self._recorded_recovery_decisions.add(identity)
            self.host.runs.append_autopilot_event(
                self.run_id,
                "campaign.recovery.selected",
                {
                    "task_id": task_id,
                    "failure_code": failure_code,
                    "attempt": attempt,
                    "step": decision.step.value,
                    "reasons": list(decision.reasons),
                },
            )
        return decision
