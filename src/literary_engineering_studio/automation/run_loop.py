"""Claimed Autopilot run coordination.

The controller owns API lifecycle, threads, durable leases, and policy
configuration.  This module owns only the loop that runs after a lease has
been claimed, so result handling can be tested without duplicating the public
Autopilot service.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Callable, Protocol

from ..advisor.creative_steward import CreativeSteward
from ..persistence.job_store import JobStore
from ..runtime.worker import AgentWorker, WorkerRunResult
from .policy import DelegationPolicy, next_revision_count
from .support import (
    _now,
    _operational_decision,
    _project_progress_fingerprint,
)

@dataclass(frozen=True)
class RouteCycle:
    """The route identity and lock owner for one worker cycle."""

    route_index: int
    planned_route: str
    route: str
    dependency_route: bool
    owner: str


class RunLoopHost(Protocol):
    """Narrow controller capabilities used by the claimed run loop."""

    store: JobStore
    execution_coordinator: Any

    def _worker(
        self,
        run_id: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AgentWorker: ...

    def _resolve_proactive_choice(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        *,
        stop: threading.Event | None = None,
    ) -> bool: ...

    def _delegate_choice(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        choice: dict[str, Any],
        *,
        task_id: str = "",
        stop: threading.Event | None = None,
    ) -> bool: ...

    def _current_choices(self, project: Path, route: str) -> list[dict[str, Any]]: ...

    def _complete_release(
        self,
        run_id: str,
        project: Path,
        run: dict[str, Any],
        policy: DelegationPolicy,
    ) -> None: ...

    def _register_no_progress(
        self,
        run_id: str,
        task_id: str,
        route: str,
        message: str,
    ) -> bool: ...

    def _pause_for(self, run_id: str, reason: str, message: str) -> None: ...


class ClaimedRunLoop:
    """Advance one durable Autopilot run while its controller owns the lease."""

    def __init__(
        self,
        host: RunLoopHost,
        *,
        run_id: str,
        project: Path,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        stop: threading.Event,
        route_order: tuple[str, ...],
        dependency_probe: Callable[[Path], bool],
    ) -> None:
        self.host = host
        self.run_id = run_id
        self.project = project
        self.policy = policy
        self.steward = steward
        self.stop = stop
        self.route_order = route_order
        self.dependency_probe = dependency_probe
        self.failure_by_task: dict[str, int] = {}

    def run(self) -> None:
        while not self.stop.is_set():
            run = self.host.store.read_autopilot_run(self.run_id)
            if self._pause_at_authorization_limit(run):
                return
            route_index = max(0, int(run.get("route_index") or 0))
            if route_index >= len(self.route_order):
                self.host._complete_release(
                    self.run_id,
                    self.project,
                    run,
                    self.policy,
                )
                return

            cycle = self._enter_route(run, route_index)
            if self._proactive_choice_stopped(cycle):
                return
            progress_before = _project_progress_fingerprint(self.project)
            result = self._execute_worker(run, cycle)
            if result is None:
                return
            result = self._recover_runtime_failure(result, cycle)
            if self._handle_result(run, cycle, result, progress_before):
                return

    def _pause_at_authorization_limit(self, run: dict[str, Any]) -> bool:
        reason = self.policy.limit_reason(run)
        if not reason:
            return False
        self.host._pause_for(
            self.run_id,
            reason,
            "自动创作已到达授权上限。",
        )
        return True

    def _enter_route(self, run: dict[str, Any], route_index: int) -> RouteCycle:
        planned_route = self.route_order[route_index]
        dependency_route = (
            planned_route == "scene-development"
            and self.dependency_probe(self.project)
        )
        route = "character-and-world-assets" if dependency_route else planned_route
        route_changed = str(run.get("current_route") or "") != route
        self.host.store.update_autopilot_run(
            self.run_id,
            current_route=route,
            current_task_id="" if route_changed else str(run.get("current_task_id") or ""),
            route_index=route_index,
        )
        if route_changed:
            data = {"route": route}
            if dependency_route:
                data["resume_route"] = planned_route
            self.host.store.append_autopilot_event(
                self.run_id,
                "route.dependency_entered" if dependency_route else "route.entered",
                data,
            )
        return RouteCycle(
            route_index=route_index,
            planned_route=planned_route,
            route=route,
            dependency_route=dependency_route,
            owner=f"autopilot:{self.run_id}",
        )

    def _proactive_choice_stopped(self, cycle: RouteCycle) -> bool:
        handled = self.host._resolve_proactive_choice(
            self.run_id,
            self.project,
            cycle.route,
            self.policy,
            self.steward,
            stop=self.stop,
        )
        current = self.host.store.read_autopilot_run(self.run_id)
        return self.stop.is_set() or (
            handled
            and current["status"] in {"complete", "paused", "blocked", "cancelled", "failed"}
            and current.get("stop_reason") != "application-restart"
        )

    def _execute_worker(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
    ) -> WorkerRunResult | None:
        coordinator = self.host.execution_coordinator
        if coordinator is not None and not coordinator.acquire(self.project, cycle.owner):
            self.host._pause_for(
                self.run_id,
                "project-busy",
                "同一作品已有另一项正式任务正在执行，请稍后继续。",
            )
            return None
        try:
            result = self.host._worker(
                self.run_id,
                cancel_event=self.stop,
            ).run_once(
                self.project,
                route=cycle.route,
                runtime_id=run["runtime"],
            )
        finally:
            if coordinator is not None:
                coordinator.release(self.project, cycle.owner)
        self.host.store.update_autopilot_run(
            self.run_id,
            current_task_id=result.task_id,
        )
        return result

    def _recover_runtime_failure(
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
        self.host.store.append_autopilot_event(
            self.run_id,
            "task.recovery_started",
            {"task_id": result.task_id, "run_root": str(result.run_root)},
        )
        coordinator = self.host.execution_coordinator
        if coordinator is not None and not coordinator.acquire(self.project, cycle.owner):
            return result
        try:
            recovered = self.host._worker(self.run_id).resume_from_run(result.run_root)
            self.host.store.append_autopilot_event(
                self.run_id,
                "task.recovery_succeeded",
                {"task_id": recovered.task_id, "status": recovered.status},
            )
            return recovered
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            self.host.store.append_autopilot_event(
                self.run_id,
                "task.recovery_rejected",
                {"task_id": result.task_id, "message": str(exc)},
            )
            return result
        finally:
            if coordinator is not None:
                coordinator.release(self.project, cycle.owner)

    def _handle_result(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
        progress_before: str,
    ) -> bool:
        if result.status == "route_ready":
            return self._handle_route_ready(cycle, result)
        if result.status == "complete":
            return self._record_progress(run, cycle, result, progress_before, emit_event=True)
        if result.status == "waiting_writeback":
            final = self._approve_writeback(run, cycle, result)
            if final is None:
                return True
            if final.status == "complete":
                return self._record_progress(run, cycle, final, progress_before, emit_event=False)
            result = final
        if result.status == "waiting_human":
            return self._handle_waiting_human(cycle, result)
        if result.status == "cancelled" or self.stop.is_set():
            return self._handle_cancelled()
        return self._handle_failure(cycle, result)

    def _handle_route_ready(
        self,
        cycle: RouteCycle,
        result: WorkerRunResult,
    ) -> bool:
        if cycle.dependency_route:
            if self.dependency_probe(self.project):
                return self.host._register_no_progress(
                    self.run_id,
                    result.task_id or f"{cycle.route}:dependency",
                    cycle.route,
                    "依赖路线报告完成，但候选资产门禁仍未解除。",
                )
            self.host.store.append_autopilot_event(
                self.run_id,
                "route.dependency_ready",
                {"route": cycle.route, "resume_route": cycle.planned_route},
            )
            self._reset_route_progress(cycle.route_index)
            return False

        self.host.store.append_autopilot_event(
            self.run_id,
            "route.ready",
            {"route": cycle.route},
        )
        self._reset_route_progress(cycle.route_index + 1)
        return False

    def _reset_route_progress(self, route_index: int) -> None:
        self.host.store.update_autopilot_run(
            self.run_id,
            route_index=route_index,
            current_task_id="",
            stalled_cycles=0,
            last_error="",
            progress_fingerprint=_project_progress_fingerprint(self.project),
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
        progress_after = _project_progress_fingerprint(self.project)
        if progress_after == progress_before:
            suffix = "writeback" if not emit_event else "unknown"
            message = (
                "写回报告完成，但正式项目没有出现新的可验证产物。"
                if not emit_event
                else "任务报告完成，但项目正式状态没有发生可验证变化。"
            )
            return self.host._register_no_progress(
                self.run_id,
                result.task_id or f"{cycle.route}:{suffix}",
                cycle.route,
                message,
            )
        self.host.store.advance_autopilot_run(
            self.run_id,
            consecutive_revisions=next_revision_count(run, result.task_id),
            failures=0,
            last_error="",
            progress_fingerprint=progress_after,
            stalled_cycles=0,
            last_progress_at=_now(),
        )
        if emit_event:
            self.host.store.append_autopilot_event(
                self.run_id,
                "progress.advanced",
                {
                    "route": cycle.route,
                    "task_id": result.task_id,
                    "fingerprint": progress_after,
                },
            )
        return False

    def _approve_writeback(
        self,
        run: dict[str, Any],
        cycle: RouteCycle,
        result: WorkerRunResult,
    ) -> WorkerRunResult | None:
        if not self.policy.permits_writeback(cycle.route):
            self.host._pause_for(
                self.run_id,
                "writeback-approval-required",
                result.message,
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
        self.host.store.record_delegated_decision(
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
        self,
        cycle: RouteCycle,
        result: WorkerRunResult,
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
                self.run_id,
                "human-decision-required",
                result.message,
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
        self.host._pause_for(
            self.run_id,
            "user-request",
            "自动创作已暂停。",
        )
        return True

    def _handle_failure(
        self,
        cycle: RouteCycle,
        result: WorkerRunResult,
    ) -> bool:
        task_key = result.task_id or f"{cycle.route}:unknown"
        failure_count = self.failure_by_task.get(task_key, 0) + 1
        self.failure_by_task[task_key] = failure_count
        self.host.store.update_autopilot_run(
            self.run_id,
            failures=failure_count,
            last_error=result.message,
        )
        self.host.store.append_autopilot_event(
            self.run_id,
            "task.failed",
            {
                "task_id": task_key,
                "status": result.status,
                "message": result.message,
            },
        )
        limit = int(self.policy.payload["limits"]["max_failures_per_task"])
        if failure_count > limit:
            self.host._pause_for(
                self.run_id,
                "repeated-task-failure",
                result.message,
            )
            return True
        time.sleep(min(5, failure_count))
        return False
