"""Durable deterministic orchestration for bounded multi-task creation runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from ..observability.agent_session_tracking import track_agent_session_event
from .decision_delegation import DecisionDelegator
from .lease_heartbeat import (
    LeaseRenewalResult,
    renew_or_reclaim_lease,
    run_lease_heartbeat,
)
from .policy import (
    DECISION_ALIASES,
    DelegationPolicy,
    MODES,
    POLICY_SCHEMA,
    REVISION_TASK_MARKERS,
    default_policy,
    is_revision_task,
    next_revision_count,
    normalize_policy,
)
from .run_loop import ClaimedRunLoop
from .support import (
    _choice_fingerprint,
    _now,
    _parse_time,
    _pending_asset_dependency,
    _validate_autopilot_project,
)
from ..projections.core_read_models import current_choices
from ..application.style.mount_service import StyleMountApplicationService
from ..advisor.creative_steward import CreativeSteward
from ..persistence.job_store import JobStore
from ..projections.whole_book_release import WholeBookReleaseCoordinator
from ..runtime.worker import AgentWorker, WorkerRunResult


ROUTE_ORDER = (
    "source-ingest", "longform-planning", "style-engineering",
    "character-and-world-assets", "scene-development", "review-and-audit",
    "export-and-release",
)
PROACTIVE_DECISIONS = {
    "branch_selection", "style_mount", "revision_direction",
    "word_budget_direction", "canon_patch_approval",
}
TERMINAL_STATUSES = {"complete", "paused", "blocked", "cancelled", "failed"}
NO_PROGRESS_LIMIT = 3

class AutopilotService:
    def __init__(
        self,
        config: dict[str, Any],
        store: JobStore,
        *,
        runtime_pool=None,
        execution_coordinator=None,
        style_mount_service: StyleMountApplicationService | None = None,
    ):
        self.config = config
        self.store = store
        self.runtime_pool = runtime_pool
        self.execution_coordinator = execution_coordinator
        self.style_mount_service = style_mount_service or StyleMountApplicationService()
        self._choice_delegator = DecisionDelegator(
            config,
            store,
            self.style_mount_service,
            self._pause_for,
        )
        self.store.recover_autopilot_runs()
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._controller_id = f"studio-controller-{uuid.uuid4().hex[:12]}"

    def policy(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        stored = self.store.read_delegation_policy(root)
        return stored or self.store.save_delegation_policy(root, default_policy())

    def save_policy(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        active = self.store.latest_autopilot_run(root)
        if active and active["status"] == "running":
            raise ValueError("请先暂停自动创作，再修改授权范围。")
        policy = normalize_policy(payload)
        saved = self.store.save_delegation_policy(root, policy)
        # A paused run keeps a policy snapshot for auditability. Updating the
        # project default alone cannot renew a cap that already stopped this
        # particular run, so reflect an explicit user change into the paused
        # run and leave a durable event explaining why it may resume.
        if active and active["status"] in {"paused", "blocked", "failed"}:
            runtime_window_started_at = _now()
            run_policy = {**policy, "runtime_window_started_at": runtime_window_started_at}
            renewed = self.store.update_autopilot_run_policy(active["run_id"], run_policy)
            # A revision cap is deliberately a per-authorization safety window:
            # its purpose is to stop an unattended run and request fresh human
            # consent, not to permanently poison the run.  Without resetting
            # this durable counter, the UI can successfully save and resume a
            # renewed policy only for the controller to pause again before it
            # is allowed to claim another task.
            if str(active.get("stop_reason") or "") == "revision-limit":
                renewed = self.store.update_autopilot_run(
                    active["run_id"],
                    consecutive_revisions=0,
                    last_error="",
                    stop_reason="",
                )
            self.store.append_autopilot_event(
                active["run_id"],
                "autopilot.authorization_updated",
                {
                    "mode": policy["mode"],
                    "limits": policy["limits"],
                    "runtime_window_started_at": runtime_window_started_at,
                    "revision_window_reset": str(active.get("stop_reason") or "") == "revision-limit",
                },
            )
            saved["run"] = renewed
        return saved

    def start(self, project_root: Path, *, runtime: str = "opencode") -> dict[str, Any]:
        root = project_root.expanduser().resolve()
        _validate_autopilot_project(root, runtime)
        active = self.store.latest_autopilot_run(str(root))
        if active and active["status"] == "running":
            return active
        policy = self.policy(root)["policy"]
        run = self.store.create_autopilot_run(str(root), mode=policy["mode"], runtime=runtime, policy=policy)
        self._launch(run["run_id"])
        return run

    def resume(self, run_id: str, *, authorized: bool = False) -> dict[str, Any]:
        run = self.store.read_autopilot_run(run_id)
        if run["status"] == "running":
            return run
        if run["status"] == "complete":
            raise ValueError("这次自动创作已经完成。")
        run_policy = run.get("policy") if isinstance(run.get("policy"), dict) else {}
        if str(run_policy.get("mode") or run.get("mode") or "") == "full_auto" and not authorized:
            raise ValueError("全自动交付需要在推进仪表中明确确认授权后才能继续。")
        _validate_autopilot_project(Path(run["project_root"]), str(run.get("runtime") or ""))
        self.store.update_autopilot_run(
            run_id,
            status="running",
            stop_reason="",
            last_error="",
            finished_at="",
        )
        self.store.append_autopilot_event(run_id, "autopilot.resumed", {})
        self._launch(run_id)
        return self.store.read_autopilot_run(run_id)

    def pause(self, run_id: str, *, reason: str = "user-request") -> dict[str, Any]:
        run = self.store.read_autopilot_run(run_id)
        with self._lock:
            stop = self._stops.get(run_id)
            if stop:
                stop.set()
        if run["status"] not in TERMINAL_STATUSES:
            self.store.update_autopilot_run(run_id, status="paused", stop_reason=reason)
            self.store.append_autopilot_event(run_id, "autopilot.paused", {"reason": reason})
        return self.store.read_autopilot_run(run_id)

    def status(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        return {
            "ok": True,
            "schema": "arcvellum/autopilot-status/v0.1",
            "policy": self.policy(project_root)["policy"],
            "run": self.store.latest_autopilot_run(root),
        }

    def shutdown(self) -> None:
        with self._lock:
            runs = list(self._stops.items())
        for run_id, stop in runs:
            stop.set()
            try:
                run = self.store.read_autopilot_run(run_id)
                if run["status"] == "running":
                    self.store.update_autopilot_run(run_id, status="paused", stop_reason="application-shutdown")
            except (FileNotFoundError, ValueError):
                pass
        for thread in list(self._threads.values()):
            thread.join(timeout=5)

    def _launch(self, run_id: str) -> None:
        with self._lock:
            existing = self._threads.get(run_id)
            if existing and existing.is_alive():
                return
            stop = threading.Event()
            self._stops[run_id] = stop
            thread = threading.Thread(target=self._run, args=(run_id, stop), name=f"arcvellum-{run_id}", daemon=True)
            self._threads[run_id] = thread
            thread.start()

    def _run(self, run_id: str, stop: threading.Event) -> None:
        """Run one controller only while this process owns the durable lease."""

        lease_owner = f"{self._controller_id}:{run_id}"
        if not self.store.acquire_autopilot_lease(run_id, lease_owner, lease_seconds=self._lease_seconds()):
            self.store.append_autopilot_event(
                run_id,
                "autopilot.controller_busy",
                {"controller_id": self._controller_id},
            )
            return
        renew_stop = threading.Event()

        heartbeat = threading.Thread(
            target=self._lease_heartbeat,
            args=(run_id, lease_owner, stop, renew_stop),
            name=f"arcvellum-lease-{run_id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            self._run_claimed(run_id, stop)
        finally:
            renew_stop.set()
            heartbeat.join(timeout=1)
            self.store.release_autopilot_lease(run_id, lease_owner)

    def _lease_seconds(self) -> int:
        application = self.config.get("application") if isinstance(self.config.get("application"), dict) else {}
        return max(30, min(900, int(application.get("lease_seconds") or 90)))

    def _renew_or_reclaim_lease(
        self,
        run_id: str,
        lease_owner: str,
    ) -> LeaseRenewalResult:
        """Renew a controller lease, reclaiming only a lease no controller owns.

        A worker can be busy in a long streamed model turn while another
        local component is writing observability events.  Treating one
        unsuccessful renewal as an immediate cancellation leaves the run
        visually ``running`` but without a controller.  Re-acquiring with the
        same owner is safe: the store rejects a live foreign owner, but lets
        this controller recover an expired or unexpectedly removed lease.
        """

        return renew_or_reclaim_lease(
            self.store,
            run_id,
            lease_owner,
            lease_seconds=self._lease_seconds(),
        )

    def _lease_heartbeat(
        self,
        run_id: str,
        lease_owner: str,
        stop: threading.Event,
        renew_stop: threading.Event,
    ) -> None:
        run_lease_heartbeat(
            self.store,
            run_id=run_id,
            lease_owner=lease_owner,
            controller_id=self._controller_id,
            stop=stop,
            renew_stop=renew_stop,
            renew=self._renew_or_reclaim_lease,
        )

    def _worker(
        self, run_id: str, *, cancel_event: threading.Event | None = None,
    ) -> AgentWorker:
        return AgentWorker(
            self.config, plan_store=self.store,
            event_sink=lambda event, data: self._worker_event(run_id, event, data),
            cancel_event=cancel_event, runtime_pool=self.runtime_pool,
        )

    def _run_claimed(self, run_id: str, stop: threading.Event) -> None:
        run = self.store.read_autopilot_run(run_id)
        project = Path(run["project_root"])
        policy = DelegationPolicy(run["policy"])
        steward = (
            CreativeSteward(self.config, runtime_pool=self.runtime_pool)
            if self.runtime_pool is not None
            else CreativeSteward(self.config)
        )
        setattr(
            steward,
            "event_sink",
            lambda event, data: self._steward_event(run_id, event, data),
        )
        try:
            ClaimedRunLoop(
                self,
                run_id=run_id,
                project=project,
                policy=policy,
                steward=steward,
                stop=stop,
                route_order=ROUTE_ORDER,
                dependency_probe=_pending_asset_dependency,
            ).run()
        except Exception as exc:
            self.store.update_autopilot_run(run_id, status="blocked", last_error=str(exc), stop_reason="controller-error", finished_at=_now())
            self.store.append_autopilot_event(run_id, "autopilot.blocked", {"message": str(exc)})
        finally:
            with self._lock:
                self._stops.pop(run_id, None)
                self._threads.pop(run_id, None)

    def _current_choices(self, project: Path, route: str) -> list[dict[str, Any]]:
        payload = current_choices(self.config, project, route=route)
        choices = payload.get("choices")
        return [item for item in choices if isinstance(item, dict)] if isinstance(choices, list) else []

    def _complete_release(
        self,
        run_id: str,
        project: Path,
        run: dict[str, Any],
        policy: DelegationPolicy,
    ) -> None:
        if policy.payload["release_policy"] != "delegated":
            self._pause_for(
                run_id,
                "release-approval-required",
                "全书已经完成正式路线，等待你批准最终交付。",
            )
            return
        release = WholeBookReleaseCoordinator(self.config).release(
            project,
            approved_by="delegated-agent:creative-steward",
            autopilot_run_id=run_id,
        )
        self.store.append_autopilot_event(run_id, "release.completed", release)
        self.store.update_autopilot_run(
            run_id,
            status="complete",
            finished_at=_now(),
            stop_reason="",
        )
        self.store.append_autopilot_event(
            run_id,
            "autopilot.completed",
            {"tasks_completed": run["tasks_completed"]},
        )
    def _resolve_proactive_choice(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        *,
        stop: threading.Event | None = None,
    ) -> bool:
        payload = current_choices(self.config, project, route=route)
        choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
        prior = {
            str(item.get("choice_fingerprint") or "")
            for item in self.store.delegated_decisions(run_id)
            if not item.get("revoked_at")
        }
        choice = next(
            (
                item
                for item in choices
                if isinstance(item, dict)
                and str(item.get("route") or "") == route
                and str(item.get("decision_type") or "") in PROACTIVE_DECISIONS
                and policy.permits(route, str(item.get("decision_type") or ""))
                and _choice_fingerprint(item) not in prior
            ),
            None,
        )
        if choice is None:
            return False
        return self._delegate_choice(run_id, project, route, policy, steward, choice, stop=stop)

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
    ) -> bool:
        return self._choice_delegator.execute(
            run_id,
            project,
            route,
            policy,
            steward,
            choice,
            task_id=task_id,
            stop=stop,
        )

    def _worker_event(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        run = self.store.read_autopilot_run(run_id)
        track_agent_session_event(
            self.store,
            project_root=str(run.get("project_root") or ""),
            role="worker",
            runtime=str(run.get("runtime") or "opencode"),
            controller_id=run_id,
            task_id=str(run.get("current_task_id") or ""),
            route=str(run.get("current_route") or ""),
            event=event,
            data=data,
        )
        if event == "task.opened":
            self.store.update_autopilot_run(
                run_id,
                current_task_id=str(data.get("task_id") or ""),
                current_route=str(data.get("route") or run.get("current_route") or ""),
            )
        if event in {"agent.message.delta", "runner.session.status"}:
            return
        self.store.append_autopilot_event(run_id, f"worker.{event}", data)
        if event == "usage.updated":
            cost = float(data.get("cost_usd") or 0)
            if cost > 0:
                run = self.store.read_autopilot_run(run_id)
                self.store.update_autopilot_run(run_id, estimated_cost=float(run["estimated_cost"]) + cost)

    def _steward_event(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        run = self.store.read_autopilot_run(run_id)
        track_agent_session_event(
            self.store,
            project_root=str(run.get("project_root") or ""),
            role="steward",
            runtime="opencode",
            controller_id=run_id,
            task_id=str(run.get("current_task_id") or ""),
            route=str(run.get("current_route") or ""),
            event=event,
            data=data,
        )
        self.store.append_autopilot_event(run_id, event, data)

    def _register_no_progress(self, run_id: str, task_id: str, route: str, message: str) -> bool:
        run = self.store.read_autopilot_run(run_id)
        stalled_cycles = int(run.get("stalled_cycles") or 0) + 1
        changes: dict[str, Any] = {
            "stalled_cycles": stalled_cycles,
            "last_error": message,
            "current_task_id": task_id,
        }
        if stalled_cycles == 2:
            changes["last_recovery_at"] = _now()
        self.store.update_autopilot_run(run_id, **changes)
        self.store.append_autopilot_event(
            run_id,
            "progress.stalled",
            {
                "route": route,
                "task_id": task_id,
                "stalled_cycles": stalled_cycles,
                "message": message,
            },
        )
        if stalled_cycles == 2:
            self.store.append_autopilot_event(
                run_id,
                "task.recovery_requested",
                {
                    "route": route,
                    "task_id": task_id,
                    "strategy": "re-open-current-formal-task",
                },
            )
        if stalled_cycles >= NO_PROGRESS_LIMIT:
            self._pause_for(
                run_id,
                "no-progress",
                f"{message} 已连续 {stalled_cycles} 次未推进；系统已暂停，避免空转消耗。",
            )
            return True
        time.sleep(0.15 * stalled_cycles)
        return False

    def _pause_for(self, run_id: str, reason: str, message: str) -> None:
        self.store.update_autopilot_run(run_id, status="paused", stop_reason=reason, last_error=message)
        self.store.append_autopilot_event(run_id, "autopilot.paused", {"reason": reason, "message": message})
