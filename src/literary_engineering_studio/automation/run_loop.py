"""Claimed Autopilot run coordination.

The controller owns API lifecycle, threads, durable leases, and policy
configuration.  This module owns only the loop that runs after a lease has
been claimed, so result handling can be tested without duplicating the public
Autopilot service.
"""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable

from ..advisor.creative_steward import CreativeSteward
from ..runtime.worker import WorkerRunResult
from .campaign_runtime import CampaignRuntimeCoordinator
from .policy import DelegationPolicy
from .run_result_handler import ClaimedRunResultHandler, RouteCycle, RunLoopHost


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
        campaign: CampaignRuntimeCoordinator | None = None,
    ) -> None:
        self.host = host
        self.run_id = run_id
        self.project = project
        self.policy = policy
        self.steward = steward
        self.stop = stop
        self.route_order = route_order
        self.dependency_probe = dependency_probe
        self.campaign = campaign
        self.results = ClaimedRunResultHandler(
            host,
            run_id=run_id,
            project=project,
            policy=policy,
            steward=steward,
            stop=stop,
            dependency_probe=dependency_probe,
            campaign=campaign,
        )

    def run(self) -> None:
        while not self.stop.is_set():
            run = self.host.runs.read_autopilot_run(self.run_id)
            if self._pause_at_authorization_limit(run):
                return
            if self._campaign_stopped(run):
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
            progress_before, _ = self.results.progress_identity()
            result = self._execute_worker(run, cycle)
            if result is None:
                return
            result = self.results.recover_runtime_failure(result, cycle)
            if self.results.handle(run, cycle, result, progress_before):
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

    def _campaign_stopped(self, run: dict[str, Any]) -> bool:
        if self.campaign is None:
            return False
        self.campaign.ensure_baseline(run)
        decision = self.campaign.step_decision(run)
        if decision.proceed:
            return False
        reason = decision.reasons[0] if decision.reasons else "campaign-blocked"
        self.host._pause_for(
            self.run_id,
            "campaign-policy",
            f"自动创作 Campaign 已停止：{reason}",
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
        self.host.runs.update_autopilot_run(
            self.run_id,
            current_route=route,
            current_task_id="" if route_changed else str(run.get("current_task_id") or ""),
            route_index=route_index,
        )
        if route_changed:
            data = {"route": route}
            if dependency_route:
                data["resume_route"] = planned_route
            self.host.runs.append_autopilot_event(
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
        current = self.host.runs.read_autopilot_run(self.run_id)
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
        self.host.runs.update_autopilot_run(
            self.run_id,
            current_task_id=result.task_id,
        )
        return result
