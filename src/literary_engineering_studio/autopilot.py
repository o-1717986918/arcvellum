"""Durable deterministic orchestration for bounded multi-task creation runs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from .core_read_models import current_choices, mount_style, record_choice
from .creative_steward import CreativeSteward, CreativeStewardCancelled
from .agent_session_tracking import track_agent_session_event
from .jobs import JobStore
from .project_manager import read_directions, record_direction
from .whole_book_release import WholeBookReleaseCoordinator
from .worker import AgentWorker, WorkerRunResult
from literary_engineering_studio_engine.workflow_state import build_workflow_state


POLICY_SCHEMA = "arcvellum/delegation-policy/v0.1"
MODES = {"collaborative", "supervised_auto", "full_auto"}
ROUTE_ORDER = (
    "source-ingest",
    "longform-planning",
    "style-engineering",
    "character-and-world-assets",
    "scene-development",
    "review-and-audit",
    "export-and-release",
)
DECISION_ALIASES = {"word_budget_direction": "budget_expansion"}
PROACTIVE_DECISIONS = {
    "branch_selection",
    "style_mount",
    "revision_direction",
    "word_budget_direction",
    "canon_patch_approval",
}
TERMINAL_STATUSES = {"complete", "paused", "blocked", "cancelled", "failed"}
REVISION_TASK_MARKERS = (
    "revision",
    "revise",
    "asset-review-pass",
    "asset-approval-revision",
    "canon-review-pass",
    "committee-pass",
)
NO_PROGRESS_LIMIT = 3
PROGRESS_ROOTS = (
    "project.yaml",
    "canon",
    "characters",
    "world",
    "plot",
    "scenes",
    "branches",
    "drafts",
    "reviews",
    "style",
    "workflow",
    "delivery",
    "releases",
)
PROGRESS_EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    "dashboard",
    "runtime_choices",
    "task_runs",
    "worker_runs",
    "logs",
}


def is_revision_task(task_id: str) -> bool:
    normalized = str(task_id or "").strip().lower()
    return bool(normalized) and any(marker in normalized for marker in REVISION_TASK_MARKERS)


def next_revision_count(run: dict[str, Any], task_id: str) -> int:
    return int(run.get("consecutive_revisions") or 0) + 1 if is_revision_task(task_id) else 0


def default_policy(mode: str = "collaborative") -> dict[str, Any]:
    normalized = mode if mode in MODES else "collaborative"
    decisions = [] if normalized == "collaborative" else [
        "branch_selection", "style_mount", "revision_direction", "budget_expansion",
        "asset_approval", "canon_patch_approval", "state_patch_confirmation",
    ]
    delegated_routes = [
        "longform-planning", "style-engineering", "character-and-world-assets",
        "scene-development", "review-and-audit",
    ]
    if normalized == "full_auto":
        delegated_routes.append("export-and-release")
    return {
        "schema": POLICY_SCHEMA,
        "version": "0.1",
        "mode": normalized,
        "delegated_routes": delegated_routes,
        "delegated_decisions": decisions,
        "limits": {
            "max_tasks": 500,
            "max_runtime_hours": 24,
            "max_consecutive_revisions": 3,
            "max_failures_per_task": 2,
            "max_cost": 100.0,
        },
        "release_policy": "delegated" if normalized == "full_auto" else "require_user",
        "expires_at": "",
    }


def normalize_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    incoming = value or {}
    mode = str(incoming.get("mode") or "collaborative")
    if mode not in MODES:
        raise ValueError("mode must be collaborative, supervised_auto, or full_auto")
    policy = default_policy(mode)
    for key in ("delegated_routes", "delegated_decisions", "release_policy", "expires_at"):
        if key in incoming:
            policy[key] = incoming[key]
    limits = {**policy["limits"], **(incoming.get("limits") if isinstance(incoming.get("limits"), dict) else {})}
    limits["max_tasks"] = max(1, min(10000, int(limits["max_tasks"])))
    limits["max_runtime_hours"] = max(0.1, min(720.0, float(limits["max_runtime_hours"])))
    limits["max_consecutive_revisions"] = max(1, min(20, int(limits["max_consecutive_revisions"])))
    limits["max_failures_per_task"] = max(0, min(10, int(limits["max_failures_per_task"])))
    limits["max_cost"] = max(0.0, min(100000.0, float(limits["max_cost"])))
    policy["limits"] = limits
    policy["delegated_routes"] = sorted({str(item) for item in policy["delegated_routes"] if str(item) in ROUTE_ORDER})
    policy["delegated_decisions"] = sorted({str(item) for item in policy["delegated_decisions"]})
    if policy["release_policy"] not in {"require_user", "delegated"}:
        raise ValueError("release_policy must be require_user or delegated")
    return policy


class DelegationPolicy:
    def __init__(self, payload: dict[str, Any]):
        # This run-only anchor is intentionally kept outside the reusable
        # project policy.  A user who renews a paused run starts a new allowed
        # runtime window instead of being charged for the days it was paused.
        self.runtime_window_started_at = str(payload.get("runtime_window_started_at") or "")
        self.payload = normalize_policy(payload)

    @property
    def mode(self) -> str:
        return str(self.payload["mode"])

    def permits(self, route: str, decision_type: str) -> bool:
        if self.mode == "collaborative" or route not in self.payload["delegated_routes"]:
            return False
        normalized = DECISION_ALIASES.get(decision_type, decision_type)
        if normalized == "release_approval":
            return self.payload["release_policy"] == "delegated"
        return normalized in self.payload["delegated_decisions"]

    def permits_writeback(self, route: str) -> bool:
        if self.mode == "collaborative" or route not in self.payload["delegated_routes"]:
            return False
        return route != "export-and-release" or self.payload["release_policy"] == "delegated"

    def limit_reason(self, run: dict[str, Any]) -> str:
        limits = self.payload["limits"]
        if int(run["tasks_completed"]) >= int(limits["max_tasks"]):
            return "task-limit"
        started = _parse_time(self.runtime_window_started_at or str(run["started_at"]))
        if started and (datetime.now(timezone.utc) - started).total_seconds() > float(limits["max_runtime_hours"]) * 3600:
            return "runtime-limit"
        if float(run["estimated_cost"]) >= float(limits["max_cost"]) > 0:
            return "cost-limit"
        if int(run["consecutive_revisions"]) >= int(limits["max_consecutive_revisions"]):
            return "revision-limit"
        expires = _parse_time(str(self.payload.get("expires_at") or ""))
        if expires and datetime.now(timezone.utc) >= expires:
            return "authorization-expired"
        return ""


class AutopilotService:
    def __init__(
        self,
        config: dict[str, Any],
        store: JobStore,
        *,
        runtime_pool=None,
        execution_coordinator=None,
    ):
        self.config = config
        self.store = store
        self.runtime_pool = runtime_pool
        self.execution_coordinator = execution_coordinator
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
            self.store.append_autopilot_event(
                active["run_id"],
                "autopilot.authorization_updated",
                {"mode": policy["mode"], "limits": policy["limits"], "runtime_window_started_at": runtime_window_started_at},
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

    def resume(self, run_id: str) -> dict[str, Any]:
        run = self.store.read_autopilot_run(run_id)
        if run["status"] == "running":
            return run
        if run["status"] == "complete":
            raise ValueError("这次自动创作已经完成。")
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
        if not self.store.acquire_autopilot_lease(run_id, lease_owner):
            self.store.append_autopilot_event(
                run_id,
                "autopilot.controller_busy",
                {"controller_id": self._controller_id},
            )
            return
        renew_stop = threading.Event()

        def renew() -> None:
            while not renew_stop.wait(20):
                if self.store.renew_autopilot_lease(run_id, lease_owner):
                    continue
                setattr(stop, "_arcvellum_lease_lost", True)
                stop.set()
                self.store.append_autopilot_event(
                    run_id,
                    "autopilot.controller_lease_lost",
                    {"controller_id": self._controller_id},
                )
                return

        heartbeat = threading.Thread(target=renew, name=f"arcvellum-lease-{run_id}", daemon=True)
        heartbeat.start()
        try:
            self._run_claimed(run_id, stop)
        finally:
            renew_stop.set()
            heartbeat.join(timeout=1)
            self.store.release_autopilot_lease(run_id, lease_owner)

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
        route_index = max(0, int(run.get("route_index") or 0))
        failure_by_task: dict[str, int] = {}
        try:
            while not stop.is_set():
                run = self.store.read_autopilot_run(run_id)
                limit_reason = policy.limit_reason(run)
                if limit_reason:
                    self._pause_for(run_id, limit_reason, "自动创作已到达授权上限。")
                    return
                if route_index >= len(ROUTE_ORDER):
                    if policy.payload["release_policy"] != "delegated":
                        self._pause_for(run_id, "release-approval-required", "全书已经完成正式路线，等待你批准最终交付。")
                        return
                    release = WholeBookReleaseCoordinator(self.config).release(
                        project,
                        approved_by="delegated-agent:creative-steward",
                        autopilot_run_id=run_id,
                    )
                    self.store.append_autopilot_event(run_id, "release.completed", release)
                    self.store.update_autopilot_run(run_id, status="complete", finished_at=_now(), stop_reason="")
                    self.store.append_autopilot_event(run_id, "autopilot.completed", {"tasks_completed": run["tasks_completed"]})
                    return

                planned_route = ROUTE_ORDER[route_index]
                dependency_route = planned_route == "scene-development" and _pending_asset_dependency(project)
                route = "character-and-world-assets" if dependency_route else planned_route
                route_changed = str(run.get("current_route") or "") != route
                self.store.update_autopilot_run(
                    run_id,
                    current_route=route,
                    current_task_id="" if route_changed else str(run.get("current_task_id") or ""),
                    route_index=route_index,
                )
                if route_changed:
                    self.store.append_autopilot_event(
                        run_id,
                        "route.dependency_entered" if dependency_route else "route.entered",
                        {"route": route, "resume_route": planned_route} if dependency_route else {"route": route},
                    )
                decision_handled = self._resolve_proactive_choice(run_id, project, route, policy, steward, stop=stop)
                current_status = self.store.read_autopilot_run(run_id)
                if stop.is_set() or (
                    decision_handled
                    and current_status["status"] in TERMINAL_STATUSES
                    and current_status.get("stop_reason") != "application-restart"
                ):
                    return
                owner = f"autopilot:{run_id}"
                if self.execution_coordinator is not None and not self.execution_coordinator.acquire(project, owner):
                    self._pause_for(run_id, "project-busy", "同一作品已有另一项正式任务正在执行，请稍后继续。")
                    return
                progress_before = _project_progress_fingerprint(project)
                try:
                    result = AgentWorker(
                        self.config,
                        event_sink=lambda event, data: self._worker_event(run_id, event, data),
                        cancel_event=stop,
                        runtime_pool=self.runtime_pool,
                    ).run_once(project, route=route, runtime_id=run["runtime"])
                finally:
                    if self.execution_coordinator is not None:
                        self.execution_coordinator.release(project, owner)
                self.store.update_autopilot_run(run_id, current_task_id=result.task_id)

                if result.status == "runtime_failed" and result.run_root is not None and not stop.is_set():
                    self.store.append_autopilot_event(
                        run_id,
                        "task.recovery_started",
                        {"task_id": result.task_id, "run_root": str(result.run_root)},
                    )
                    if self.execution_coordinator is None or self.execution_coordinator.acquire(project, owner):
                        try:
                            result = AgentWorker(
                                self.config,
                                event_sink=lambda event, data: self._worker_event(run_id, event, data),
                                runtime_pool=self.runtime_pool,
                            ).resume_from_run(result.run_root)
                            self.store.append_autopilot_event(
                                run_id,
                                "task.recovery_succeeded",
                                {"task_id": result.task_id, "status": result.status},
                            )
                        except (FileNotFoundError, RuntimeError, ValueError) as exc:
                            self.store.append_autopilot_event(
                                run_id,
                                "task.recovery_rejected",
                                {"task_id": result.task_id, "message": str(exc)},
                            )
                        finally:
                            if self.execution_coordinator is not None:
                                self.execution_coordinator.release(project, owner)

                if result.status == "route_ready":
                    if dependency_route:
                        if _pending_asset_dependency(project):
                            if self._register_no_progress(
                                run_id,
                                result.task_id or f"{route}:dependency",
                                route,
                                "依赖路线报告完成，但候选资产门禁仍未解除。",
                            ):
                                return
                            continue
                        self.store.append_autopilot_event(
                            run_id,
                            "route.dependency_ready",
                            {"route": route, "resume_route": planned_route},
                        )
                        self.store.update_autopilot_run(
                            run_id,
                            stalled_cycles=0,
                            last_error="",
                            progress_fingerprint=_project_progress_fingerprint(project),
                            last_progress_at=_now(),
                        )
                        continue
                    self.store.append_autopilot_event(run_id, "route.ready", {"route": route})
                    route_index += 1
                    self.store.update_autopilot_run(
                        run_id,
                        route_index=route_index,
                        current_task_id="",
                        stalled_cycles=0,
                        last_error="",
                        progress_fingerprint=_project_progress_fingerprint(project),
                        last_progress_at=_now(),
                    )
                    continue
                if result.status == "complete":
                    progress_after = _project_progress_fingerprint(project)
                    if progress_after == progress_before:
                        if self._register_no_progress(
                            run_id,
                            result.task_id or f"{route}:unknown",
                            route,
                            "任务报告完成，但项目正式状态没有发生可验证变化。",
                        ):
                            return
                        continue
                    self.store.advance_autopilot_run(
                        run_id,
                        consecutive_revisions=next_revision_count(run, result.task_id),
                        failures=0,
                        last_error="",
                        progress_fingerprint=progress_after,
                        stalled_cycles=0,
                        last_progress_at=_now(),
                    )
                    self.store.append_autopilot_event(
                        run_id,
                        "progress.advanced",
                        {"route": route, "task_id": result.task_id, "fingerprint": progress_after},
                    )
                    continue
                if result.status == "waiting_writeback":
                    if not policy.permits_writeback(route):
                        self._pause_for(run_id, "writeback-approval-required", result.message)
                        return
                    if self.execution_coordinator is not None and not self.execution_coordinator.acquire(project, owner):
                        self._pause_for(run_id, "project-busy", "正式写回前发现另一项任务正在使用作品，请稍后继续。")
                        return
                    try:
                        final = AgentWorker(
                            self.config,
                            event_sink=lambda event, data: self._worker_event(run_id, event, data),
                            runtime_pool=self.runtime_pool,
                        ).approve_writeback(
                            result.run_root,
                            approved_by="delegated-agent:autopilot-controller",
                        )
                    finally:
                        if self.execution_coordinator is not None:
                            self.execution_coordinator.release(project, owner)
                    self.store.record_delegated_decision(
                        run_id,
                        _operational_decision(run, route, result.task_id, "writeback_approval", "approve", "授权策略允许导入已校验的预期产物。"),
                    )
                    if final.status == "complete":
                        progress_after = _project_progress_fingerprint(project)
                        if progress_after == progress_before:
                            if self._register_no_progress(
                                run_id,
                                result.task_id or f"{route}:writeback",
                                route,
                                "写回报告完成，但正式项目没有出现新的可验证产物。",
                            ):
                                return
                            continue
                        self.store.advance_autopilot_run(
                            run_id,
                            consecutive_revisions=next_revision_count(run, result.task_id),
                            failures=0,
                            progress_fingerprint=progress_after,
                            stalled_cycles=0,
                            last_progress_at=_now(),
                        )
                        continue
                    result = final
                if result.status == "waiting_human":
                    choices = current_choices(self.config, project, route=route).get("choices") or []
                    choice = next((item for item in choices if isinstance(item, dict) and (not result.task_id or not item.get("task_id") or item.get("task_id") == result.task_id)), None)
                    if not choice or not policy.permits(route, str(choice.get("decision_type") or "")):
                        self._pause_for(run_id, "human-decision-required", result.message)
                        return
                    if not self._delegate_choice(run_id, project, route, policy, steward, choice, task_id=result.task_id, stop=stop):
                        return
                    continue

                if result.status == "cancelled" or stop.is_set():
                    if getattr(stop, "_arcvellum_lease_lost", False):
                        return
                    self._pause_for(run_id, "user-request", "自动创作已暂停。")
                    return
                task_key = result.task_id or f"{route}:unknown"
                failure_by_task[task_key] = failure_by_task.get(task_key, 0) + 1
                self.store.update_autopilot_run(
                    run_id,
                    failures=failure_by_task[task_key],
                    last_error=result.message,
                )
                self.store.append_autopilot_event(run_id, "task.failed", {"task_id": task_key, "status": result.status, "message": result.message})
                if failure_by_task[task_key] > int(policy.payload["limits"]["max_failures_per_task"]):
                    self._pause_for(run_id, "repeated-task-failure", result.message)
                    return
                time.sleep(min(5, failure_by_task[task_key]))
        except Exception as exc:
            self.store.update_autopilot_run(run_id, status="blocked", last_error=str(exc), stop_reason="controller-error", finished_at=_now())
            self.store.append_autopilot_event(run_id, "autopilot.blocked", {"message": str(exc)})
        finally:
            with self._lock:
                self._stops.pop(run_id, None)
                self._threads.pop(run_id, None)
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
        decision_type = str(choice.get("decision_type") or "")
        if not policy.permits(route, decision_type):
            self._pause_for(run_id, "human-decision-required", "当前决定不在自动授权范围内。")
            return False
        if stop is not None and stop.is_set():
            return False
        self.store.append_autopilot_event(
            run_id,
            "decision.started",
            {
                "route": route,
                "task_id": task_id or str(choice.get("task_id") or ""),
                "decision_type": decision_type,
                "choice_id": str(choice.get("choice_id") or ""),
            },
        )
        try:
            decision = _run_steward_decision(steward, project, choice, _project_direction(project), stop)
        except CreativeStewardCancelled:
            self.store.append_autopilot_event(run_id, "decision.cancelled", {"decision_type": decision_type})
            return False
        if stop is not None and stop.is_set():
            self.store.append_autopilot_event(run_id, "decision.cancelled", {"decision_type": decision_type})
            return False
        if decision["requires_human"]:
            self._pause_for(run_id, "steward-escalation", decision["human_reason"] or "创作代理认为需要你来决定。")
            return True

        materialize = decision_type in {
            "branch_selection",
            "asset_approval",
            "release_approval",
            "canon_patch_approval",
            "state_patch_confirmation",
        }
        recorded = record_choice(
            self.config,
            project,
            {
                **choice,
                "task_id": task_id or str(choice.get("task_id") or ""),
                "selected": decision["selected_option"],
                "rationale": decision["rationale"],
                "actor": "delegated-agent:creative-steward",
                "materialize": materialize,
            },
        )
        applied_evidence: list[str] = [str(recorded.get("choice_path") or "")]
        if recorded.get("materialized"):
            applied_evidence.append(str(recorded["materialized"]))
        if decision_type in {"revision_direction", "word_budget_direction"}:
            direction = record_direction(
                project,
                _delegated_direction_message(choice, decision),
                actor="delegated-agent:creative-steward",
            )
            applied_evidence.append(str(direction.get("digest") or ""))
        elif decision_type == "style_mount":
            mounted = mount_style(
                self.config,
                project,
                str((project / "style").resolve()),
                str(decision["selected_option"]),
            )
            applied_evidence.extend(
                str(mounted.get(key) or "")
                for key in ("mount_manifest", "project_style")
                if mounted.get(key)
            )

        decision_record = {
            **decision,
            "project_root": str(project),
            "delegation_id": run_id,
            "policy_version": policy.payload["version"],
            "route": route,
            "task_id": task_id,
            "selected_option": decision["selected_option"],
            "choice_fingerprint": _choice_fingerprint(choice),
            "choice_evidence": [item for item in applied_evidence if item],
        }
        self.store.record_delegated_decision(run_id, decision_record)
        return True

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


def _run_steward_decision(
    steward: CreativeSteward,
    project: Path,
    choice: dict[str, Any],
    project_direction: str,
    stop: threading.Event | None,
) -> dict[str, Any]:
    """Preserve compatibility with test or third-party steward adapters."""

    parameters = inspect.signature(steward.decide).parameters
    kwargs: dict[str, Any] = {"project_direction": project_direction}
    if "cancel_event" in parameters:
        kwargs["cancel_event"] = stop
    return steward.decide(project, choice, **kwargs)


def _pending_asset_dependency(project: Path) -> bool:
    """Return whether scene work must yield to a formal candidate-asset gate."""

    try:
        state = build_workflow_state(project, route="character-and-world-assets")
        payload = json.loads(state.json_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    assets = payload.get("assets") if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict)
        and bool(str(item.get("candidate") or "").strip())
        and str(item.get("status") or "") != "ready"
        for item in assets
    )


def _validate_autopilot_project(project: Path, runtime: str) -> None:
    if not project.is_dir() or not (project / "project.yaml").is_file():
        raise ValueError("自动创作需要先选择一个包含 project.yaml 的有效作品目录。")
    if not str(runtime or "").strip():
        raise ValueError("自动创作需要一个可用的 Agent Runtime。")


def _project_progress_fingerprint(project: Path) -> str:
    """Hash formal project evidence without reading manuscript bodies into memory."""

    entries: list[str] = []
    for relative in PROGRESS_ROOTS:
        root = project / relative
        candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
        for path in candidates:
            if not path.is_file():
                continue
            rel = path.relative_to(project)
            if any(part.lower() in PROGRESS_EXCLUDED_PARTS for part in rel.parts):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(f"{rel.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _operational_decision(run: dict[str, Any], route: str, task_id: str, decision_type: str, selected: str, rationale: str) -> dict[str, Any]:
    return {
        "project_root": run["project_root"],
        "principal_type": "delegated-agent",
        "principal_id": "autopilot-controller",
        "delegation_id": run["run_id"],
        "policy_version": run["policy"].get("version", "0.1"),
        "route": route,
        "task_id": task_id,
        "decision_type": decision_type,
        "selected_option": selected,
        "rationale": rationale,
        "evidence": [],
        "alternatives": [],
        "confidence": 1.0,
    }


def _project_direction(project: Path) -> str:
    values = read_directions(project, limit=12)
    if not isinstance(values, list):
        return ""
    return "\n".join(str(item.get("message") or "") for item in values if isinstance(item, dict) and item.get("message"))[-6000:]


def _choice_fingerprint(choice: dict[str, Any]) -> str:
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    payload = {
        "route": str(choice.get("route") or ""),
        "decision_type": str(choice.get("decision_type") or ""),
        "target": {str(key): str(value) for key, value in sorted(target.items())},
        "options": [str(item.get("id") or "") for item in options if isinstance(item, dict)],
        "source_paths": [str(item) for item in choice.get("source_paths") or []],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _delegated_direction_message(choice: dict[str, Any], decision: dict[str, Any]) -> str:
    options = choice.get("options") if isinstance(choice.get("options"), list) else []
    selected = str(decision.get("selected_option") or "")
    option = next((item for item in options if isinstance(item, dict) and str(item.get("id") or "") == selected), {})
    label = str(option.get("label") or selected)
    rationale = str(decision.get("rationale") or "").strip()
    title = str(choice.get("title") or "当前创作节点")
    return f"创作代理已在授权范围内决定：{title}选择‘{label}’。执行后续任务时必须落实该方向。理由：{rationale}"


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
