"""Formal workflow dashboard, task summary, and human-decision routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from ..common import call_handler, project_root as resolve_project_root


@dataclass(frozen=True)
class WorkflowRouterDependencies:
    config: dict[str, Any]
    lifecycle: Any
    autopilot: Any
    cached_read_model: Callable[..., dict[str, Any]]
    dashboard_snapshot: Callable[[Path], dict[str, Any]]
    build_activity: Callable[..., dict[str, Any]]
    build_task_summary: Callable[[dict[str, Any], Path, str], dict[str, Any]]
    current_choices: Callable[..., dict[str, Any]]
    record_choice: Callable[[dict[str, Any], Path, dict[str, Any]], dict[str, Any]]
    stream_read_model: Callable[[str, Callable[[], dict[str, Any]], float, int], Any]


def build_workflow_router(deps: WorkflowRouterDependencies) -> APIRouter:
    """Build UI workflow routes without duplicating Engine state derivation."""

    router = APIRouter()

    @router.get("/workflow/dashboard")
    def workflow_dashboard(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.dashboard_snapshot(root))

    @router.get("/workflow/dashboard/stream")
    def workflow_dashboard_stream(project_root: str, interval_seconds: float = 8.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model("dashboard", lambda: deps.dashboard_snapshot(root), interval_seconds, max_events)

    @router.get("/workflow/activity")
    def workflow_activity(project_root: str, limit: int = 30):
        root = resolve_project_root(project_root)
        bounded = max(1, min(200, limit))
        return call_handler(
            lambda: deps.cached_read_model(
                f"activity:{root}:{bounded}", root, lambda: deps.build_activity(deps.config, root, bounded)
            )
        )

    @router.get("/workflow/activity/stream")
    def workflow_activity_stream(project_root: str, interval_seconds: float = 4.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model(
            "activity",
            lambda: deps.cached_read_model(f"activity:{root}:30", root, lambda: deps.build_activity(deps.config, root)),
            interval_seconds,
            max_events,
        )

    @router.get("/workflow/task-package")
    def workflow_task_package(project_root: str, task_id: str):
        return call_handler(lambda: deps.build_task_summary(deps.config, resolve_project_root(project_root), task_id))

    @router.get("/workflow/current-choice")
    def workflow_current_choice(project_root: str):
        root = resolve_project_root(project_root)

        def build_choices():
            snapshot = deps.dashboard_snapshot(root)
            dashboard = snapshot.get("dashboard") if isinstance(snapshot, dict) else None
            return deps.current_choices(deps.config, root, dashboard=dashboard if isinstance(dashboard, dict) else None)

        return call_handler(build_choices)

    @router.post("/workflow/human-choice")
    def workflow_human_choice(payload: dict[str, Any]):
        root = resolve_project_root(str(payload.get("project_root") or ""))
        result = call_handler(lambda: deps.record_choice(deps.config, root, payload))
        choice = result.get("choice") if isinstance(result.get("choice"), dict) else {}
        resumed_run: dict[str, Any] | None = None
        if result.get("consumed") is True:
            autopilot_status = deps.autopilot.status(root)
            active_run = autopilot_status.get("run") if isinstance(autopilot_status.get("run"), dict) else {}
            if active_run.get("status") == "paused" and active_run.get("stop_reason") in {"human-decision-required", "steward-escalation"}:
                resumed_run = deps.autopilot.resume(str(active_run.get("run_id") or ""), authorized=True)
        deps.lifecycle.live_events.publish(
            f"project:{root}",
            "human.choice_recorded",
            {
                "choice_id": str(choice.get("choice_id") or ""),
                "receipt_id": str(result.get("receipt_id") or ""),
                "decision_type": str(choice.get("decision_type") or ""),
                "consumed": bool(result.get("consumed")),
                "effect": result.get("effect") or {},
            },
        )
        deps.lifecycle.live_events.notify()
        result["autopilot_resumed"] = bool(resumed_run)
        if resumed_run:
            result["autopilot_run_id"] = str(resumed_run.get("run_id") or "")
        return result

    return router
