"""Durable deterministic orchestration for bounded multi-task creation runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from ..observability.event_policy import EventDurability, classify_runtime_event
from ..observability.creative_live.contracts import project_channel
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
from .campaign_runtime import CampaignRuntimeCoordinator
from .support import (
    _choice_fingerprint,
    _now,
    _parse_time,
    _pending_asset_dependency,
    _validate_autopilot_project,
)
from ..projections.core_read_models import current_choices
from ..runtime.runtime_selection import DEFAULT_CREATIVE_RUNTIME, runtime_for_role
from ..application.style.mount_service import StyleMountApplicationService
from ..application.autopilot_dependencies import resolve_autopilot_persistence
from ..application.failures import present_run
from ..advisor.creative_steward import CreativeSteward
from ..projections.whole_book_release import WholeBookReleaseCoordinator
from ..runtime.worker import AgentWorker, WorkerRunResult
from ..runtime.prepared_context_cache import PreparedContextCache
from ..orchestration import orchestration_settings, recovery_step


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
        store: Any | None = None,
        *,
        runs=None, sessions=None, plans=None, session_event_tracker=None,
        runtime_pool=None,
        execution_coordinator=None,
        style_mount_service: StyleMountApplicationService | None = None,
        prepared_context_cache: PreparedContextCache | None = None,
        live_events=None,
    ):
        self.config = config
        persistence = resolve_autopilot_persistence(
            store, runs=runs, sessions=sessions, plans=plans, session_event_tracker=session_event_tracker)
        self.runs, self.sessions, self.plans = persistence.runs, persistence.sessions, persistence.plans
        self._session_event_tracker = persistence.session_event_tracker
        self.runtime_pool = runtime_pool
        self.execution_coordinator = execution_coordinator
        self.style_mount_service = style_mount_service or StyleMountApplicationService()
        self.prepared_context_cache = prepared_context_cache
        self.live_events = live_events
        self._choice_delegator = DecisionDelegator(
            config,
            self.runs,
            self.style_mount_service,
            self._pause_for,
        )
        self.runs.recover_autopilot_runs()
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}
        self._controller_id = f"studio-controller-{uuid.uuid4().hex[:12]}"

    def policy(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        stored = self.sessions.read_delegation_policy(root)
        if stored is None:
            return self.sessions.save_delegation_policy(root, default_policy())
        return {**stored, "policy": normalize_policy(stored.get("policy"))}

    def save_policy(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        active = self.runs.latest_autopilot_run(root)
        if active and active["status"] == "running":
            raise ValueError("请先暂停自动创作，再修改创作模式。")
        policy = normalize_policy(payload)
        saved = self.sessions.save_delegation_policy(root, policy)
        # A paused run keeps a policy snapshot for auditability. Reflect an
        # explicit mode or delegation change into that run so resume uses the
        # same policy the user can see in the control panel.
        if active and active["status"] in {"paused", "blocked", "failed"}:
            renewed = self.runs.update_autopilot_run_policy(active["run_id"], policy)
            self.runs.append_autopilot_event(
                active["run_id"],
                "autopilot.policy_updated",
                {
                    "mode": policy["mode"],
                    "limits": policy["limits"],
                },
            )
            saved["run"] = renewed
        return saved

    def start(self, project_root: Path, *, runtime: str = DEFAULT_CREATIVE_RUNTIME) -> dict[str, Any]:
        root = project_root.expanduser().resolve()
        _validate_autopilot_project(root, runtime)
        active = self.runs.latest_autopilot_run(str(root))
        if active and active["status"] == "running":
            return active
        policy = self.policy(root)["policy"]
        run = self.runs.create_autopilot_run(str(root), mode=policy["mode"], runtime=runtime, policy=policy)
        self._launch(run["run_id"])
        return run

    def resume(self, run_id: str, *, authorized: bool = False) -> dict[str, Any]:
        run = self.runs.read_autopilot_run(run_id)
        if run["status"] == "running":
            return run
        if run["status"] == "complete":
            raise ValueError("这次自动创作已经完成。")
        run_policy = run.get("policy") if isinstance(run.get("policy"), dict) else {}
        if str(run_policy.get("mode") or run.get("mode") or "") == "full_auto" and not authorized:
            raise ValueError("全自动交付需要在推进仪表中明确确认授权后才能继续。")
        _validate_autopilot_project(Path(run["project_root"]), str(run.get("runtime") or ""))
        quality_retry = str(run.get("stop_reason") or "") == "revision-limit"
        self.runs.update_autopilot_run(
            run_id,
            status="running",
            stop_reason="",
            last_error="",
            finished_at="",
            **({"consecutive_revisions": 0} if quality_retry else {}),
        )
        self.runs.append_autopilot_event(
            run_id,
            "autopilot.resumed",
            {"quality_retry_reset": quality_retry},
        )
        self._launch(run_id)
        return self.runs.read_autopilot_run(run_id)

    def pause(self, run_id: str, *, reason: str = "user-request") -> dict[str, Any]:
        run = self.runs.read_autopilot_run(run_id)
        with self._lock:
            stop = self._stops.get(run_id)
            if stop:
                stop.set()
        if run["status"] not in TERMINAL_STATUSES:
            self.runs.update_autopilot_run(run_id, status="paused", stop_reason=reason)
            self.runs.append_autopilot_event(run_id, "autopilot.paused", {"reason": reason})
        return self.runs.read_autopilot_run(run_id)

    def status(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        return {
            "ok": True,
            "schema": "arcvellum/autopilot-status/v0.2",
            "policy": self.policy(project_root)["policy"],
            "run": present_run(self.runs.latest_autopilot_run(root)),
        }

    def shutdown(self) -> None:
        with self._lock:
            runs = list(self._stops.items())
        for run_id, stop in runs:
            stop.set()
            try:
                run = self.runs.read_autopilot_run(run_id)
                if run["status"] == "running":
                    self.runs.update_autopilot_run(run_id, status="paused", stop_reason="application-shutdown")
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
        if not self.runs.acquire_autopilot_lease(run_id, lease_owner, lease_seconds=self._lease_seconds()):
            self.runs.append_autopilot_event(
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
            self.runs.release_autopilot_lease(run_id, lease_owner)

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
            self.runs,
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
            self.runs,
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
            self.config, plan_store=self.plans,
            event_sink=lambda event, data: self._worker_event(run_id, event, data),
            cancel_event=cancel_event, runtime_pool=self.runtime_pool,
            prepared_context_cache=self.prepared_context_cache,
        )

    def _run_claimed(self, run_id: str, stop: threading.Event) -> None:
        run = self.runs.read_autopilot_run(run_id)
        project = Path(run["project_root"])
        policy = DelegationPolicy(run["policy"])
        settings = orchestration_settings(self.config)
        campaign = (
            CampaignRuntimeCoordinator(
                self.runs,
                project,
                run_id,
                max_autonomous_steps=None,
                checkpoint_interval_steps=(
                    settings.campaign_checkpoint_interval_steps
                ),
            )
            if settings.enabled and settings.campaign_runtime
            else None
        )
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
                campaign=campaign,
            ).run()
        except Exception as exc:
            self.runs.update_autopilot_run(run_id, status="blocked", last_error=str(exc), stop_reason="controller-error", finished_at=_now())
            self.runs.append_autopilot_event(run_id, "autopilot.blocked", {"message": str(exc)})
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
        self.runs.append_autopilot_event(run_id, "release.completed", release)
        self.runs.update_autopilot_run(
            run_id,
            status="complete",
            finished_at=_now(),
            stop_reason="",
        )
        self.runs.append_autopilot_event(
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
            for item in self.runs.delegated_decisions(run_id)
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
        run = self.runs.read_autopilot_run(run_id)
        enriched = _runtime_event_context(run, event, data)
        self._session_event_tracker(
            project_root=str(run.get("project_root") or ""),
            role="worker",
            runtime=str(run.get("runtime") or DEFAULT_CREATIVE_RUNTIME),
            controller_id=run_id,
            task_id=str(run.get("current_task_id") or ""),
            route=str(run.get("current_route") or ""),
            event=event,
            data=enriched,
        )
        if event == "task.opened":
            self.runs.update_autopilot_run(
                run_id,
                current_task_id=str(data.get("task_id") or ""),
                current_route=str(data.get("route") or run.get("current_route") or ""),
            )
        if self.live_events is not None:
            self.live_events.publish(
                project_channel(str(run.get("project_root") or "")), event, enriched
            )
        if classify_runtime_event(event) is EventDurability.EPHEMERAL:
            if self.live_events is not None:
                self.live_events.publish(f"autopilot:{run_id}", event, enriched)
            return
        self.runs.append_autopilot_event(run_id, f"worker.{event}", enriched)
        if event == "usage.updated":
            cost = float(data.get("cost_usd") or 0)
            if cost > 0:
                run = self.runs.read_autopilot_run(run_id)
                self.runs.update_autopilot_run(run_id, estimated_cost=float(run["estimated_cost"]) + cost)

    def _steward_event(self, run_id: str, event: str, data: dict[str, Any]) -> None:
        run = self.runs.read_autopilot_run(run_id)
        enriched = _runtime_event_context(run, event, data)
        self._session_event_tracker(
            project_root=str(run.get("project_root") or ""),
            role="steward",
            runtime=runtime_for_role(self.config, "steward"),
            controller_id=run_id,
            task_id=str(run.get("current_task_id") or ""),
            route=str(run.get("current_route") or ""),
            event=event,
            data=enriched,
        )
        self.runs.append_autopilot_event(run_id, event, enriched)
        if self.live_events is not None:
            self.live_events.publish(
                project_channel(str(run.get("project_root") or "")), event, enriched
            )

    def _register_no_progress(self, run_id: str, task_id: str, route: str, message: str) -> bool:
        run = self.runs.read_autopilot_run(run_id)
        stalled_cycles = int(run.get("stalled_cycles") or 0) + 1
        changes: dict[str, Any] = {
            "stalled_cycles": stalled_cycles,
            "last_error": message,
            "current_task_id": task_id,
        }
        if stalled_cycles == 2:
            changes["last_recovery_at"] = _now()
            if self._campaign_runtime_enabled():
                changes["current_task_id"] = ""
        self.runs.update_autopilot_run(run_id, **changes)
        self.runs.append_autopilot_event(
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
            self.runs.append_autopilot_event(
                run_id,
                "task.recovery_requested",
                {
                    "route": route,
                    "task_id": task_id,
                    "strategy": "re-open-current-formal-task",
                },
            )
        if self._campaign_runtime_enabled() and stalled_cycles >= 2:
            attempt = 1 if stalled_cycles < NO_PROGRESS_LIMIT else 2
            decision = recovery_step("no_progress", attempt)
            self.runs.append_autopilot_event(
                run_id,
                "campaign.recovery.selected",
                {
                    "task_id": task_id,
                    "failure_code": "no_progress",
                    "attempt": attempt,
                    "step": decision.step.value,
                    "reasons": list(decision.reasons),
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

    def _campaign_runtime_enabled(self) -> bool:
        settings = orchestration_settings(self.config)
        return settings.enabled and settings.campaign_runtime

    def _pause_for(self, run_id: str, reason: str, message: str) -> None:
        self.runs.update_autopilot_run(run_id, status="paused", stop_reason=reason, last_error=message)
        self.runs.append_autopilot_event(run_id, "autopilot.paused", {"reason": reason, "message": message})


def _runtime_event_context(
    run: dict[str, Any], event: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Attach stable identities without mutating the provider-owned payload."""

    result = dict(data)
    result.setdefault("runtime_event_id", uuid.uuid4().hex)
    result.setdefault("run_id", str(run.get("run_id") or ""))
    result.setdefault("controller_id", str(run.get("run_id") or ""))
    result.setdefault("task_id", str(run.get("current_task_id") or ""))
    result.setdefault("route", str(run.get("current_route") or ""))
    result.setdefault("runtime", str(run.get("runtime") or DEFAULT_CREATIVE_RUNTIME))
    result.setdefault(
        "attempt_id", str(result.get("run_id") or run.get("run_id") or "")
    )
    result.setdefault("source_event", event)
    return result
