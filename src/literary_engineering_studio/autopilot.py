"""Durable deterministic orchestration for bounded multi-task creation runs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any

from .core_read_models import current_choices, mount_style, record_choice
from .creative_steward import CreativeSteward
from .jobs import JobStore
from .project_manager import read_directions, record_direction
from .whole_book_release import WholeBookReleaseCoordinator
from .worker import AgentWorker, WorkerRunResult


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
        started = _parse_time(str(run["started_at"]))
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
    def __init__(self, config: dict[str, Any], store: JobStore):
        self.config = config
        self.store = store
        self.store.recover_autopilot_runs()
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._stops: dict[str, threading.Event] = {}

    def policy(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        stored = self.store.read_delegation_policy(root)
        return stored or self.store.save_delegation_policy(root, default_policy())

    def save_policy(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        active = self.store.latest_autopilot_run(root)
        if active and active["status"] == "running":
            raise ValueError("请先暂停自动创作，再修改授权范围。")
        return self.store.save_delegation_policy(root, normalize_policy(payload))

    def start(self, project_root: Path, *, runtime: str = "opencode") -> dict[str, Any]:
        root = project_root.expanduser().resolve()
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
        self.store.update_autopilot_run(run_id, status="running", stop_reason="", last_error="")
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
        run = self.store.read_autopilot_run(run_id)
        project = Path(run["project_root"])
        policy = DelegationPolicy(run["policy"])
        steward = CreativeSteward(self.config)
        route_index = 0
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

                route = ROUTE_ORDER[route_index]
                self.store.update_autopilot_run(run_id, current_route=route, current_task_id="")
                self.store.append_autopilot_event(run_id, "route.entered", {"route": route})
                if self._resolve_proactive_choice(run_id, project, route, policy, steward):
                    if self.store.read_autopilot_run(run_id)["status"] != "running":
                        return
                result = AgentWorker(
                    self.config,
                    event_sink=lambda event, data: self._worker_event(run_id, event, data),
                    cancel_event=stop,
                ).run_once(project, route=route, runtime_id=run["runtime"])
                self.store.update_autopilot_run(run_id, current_task_id=result.task_id)

                if result.status == "route_ready":
                    self.store.append_autopilot_event(run_id, "route.ready", {"route": route})
                    route_index += 1
                    continue
                if result.status == "complete":
                    revisions = int(run["consecutive_revisions"]) + 1 if "revis" in result.task_id.lower() else 0
                    self.store.update_autopilot_run(
                        run_id,
                        tasks_completed=int(run["tasks_completed"]) + 1,
                        consecutive_revisions=revisions,
                        failures=0,
                        last_error="",
                    )
                    continue
                if result.status == "waiting_writeback":
                    if not policy.permits_writeback(route):
                        self._pause_for(run_id, "writeback-approval-required", result.message)
                        return
                    final = AgentWorker(self.config, event_sink=lambda event, data: self._worker_event(run_id, event, data)).approve_writeback(
                        result.run_root,
                        approved_by="delegated-agent:autopilot-controller",
                    )
                    self.store.record_delegated_decision(
                        run_id,
                        _operational_decision(run, route, result.task_id, "writeback_approval", "approve", "授权策略允许导入已校验的预期产物。"),
                    )
                    if final.status == "complete":
                        self.store.update_autopilot_run(run_id, tasks_completed=int(run["tasks_completed"]) + 1, failures=0)
                        continue
                    result = final
                if result.status == "waiting_human":
                    choices = current_choices(self.config, project).get("choices") or []
                    choice = next((item for item in choices if isinstance(item, dict) and (not result.task_id or not item.get("task_id") or item.get("task_id") == result.task_id)), None)
                    if not choice or not policy.permits(route, str(choice.get("decision_type") or "")):
                        self._pause_for(run_id, "human-decision-required", result.message)
                        return
                    if not self._delegate_choice(run_id, project, route, policy, steward, choice, task_id=result.task_id):
                        return
                    continue

                if result.status == "cancelled" or stop.is_set():
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
    ) -> bool:
        payload = current_choices(self.config, project)
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
        return self._delegate_choice(run_id, project, route, policy, steward, choice)

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
    ) -> bool:
        decision_type = str(choice.get("decision_type") or "")
        if not policy.permits(route, decision_type):
            self._pause_for(run_id, "human-decision-required", "当前决定不在自动授权范围内。")
            return False
        decision = steward.decide(project, choice, project_direction=_project_direction(project))
        if decision["requires_human"]:
            self._pause_for(run_id, "steward-escalation", decision["human_reason"] or "创作代理认为需要你来决定。")
            return False

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
        self.store.append_autopilot_event(run_id, f"worker.{event}", data)
        if event == "usage.updated":
            cost = float(data.get("cost_usd") or 0)
            if cost > 0:
                run = self.store.read_autopilot_run(run_id)
                self.store.update_autopilot_run(run_id, estimated_cost=float(run["estimated_cost"]) + cost)

    def _pause_for(self, run_id: str, reason: str, message: str) -> None:
        self.store.update_autopilot_run(run_id, status="paused", stop_reason=reason, last_error=message)
        self.store.append_autopilot_event(run_id, "autopilot.paused", {"reason": reason, "message": message})


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
