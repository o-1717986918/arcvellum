"""Pure workflow dashboard projection for UI and streaming readers."""

from __future__ import annotations

from pathlib import Path

from ..task_registry import SUPPORTED_ROUTES
from .audit.task_status import project_agent_task_status, project_route_audit
from .dashboard import (
    WORKFLOW_DASHBOARD_SCHEMA,
    _authority_hierarchy,
    _next_actions,
    _now,
    _read_events,
    _route_audit_summary,
    _summary,
)
from .state import project_workflow_state


def project_workflow_dashboard(project_root: Path) -> dict[str, object]:
    """Return the current dashboard without writing derived project files."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    state_payload = project_workflow_state(
        root,
        route="overall",
        scene_scope="dashboard",
    )
    task_payload = project_agent_task_status(root)
    route_audits = [
        project_route_audit(root, route=route)
        for route in sorted(SUPPORTED_ROUTES)
    ]
    next_actions = _next_actions(state_payload, route_audits)
    summary = _summary(state_payload, task_payload, route_audits, next_actions)
    return {
        "schema": WORKFLOW_DASHBOARD_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "authority_hierarchy": _authority_hierarchy(),
        "route_state": {
            "path": "workflow/dashboard/route_state.json",
            "summary": state_payload.get("summary", {}),
        },
        "agent_task_status": {
            "path": "workflow/dashboard/agent_task_status.json",
            "summary": task_payload.get("summary", {}),
        },
        "route_audits": [_route_audit_summary(root, audit) for audit in route_audits],
        "next_actions": next_actions,
        "recent_events": _read_events(root / "workflow" / "events" / "task_events.jsonl")[-25:],
        "frontend": {
            "html": "workflow/dashboard/workflow_dashboard.html",
            "json": "workflow/dashboard/workflow_dashboard.json",
            "mode": "pure live projection; run workflow-dashboard to materialize portable files",
        },
        "rules": [
            "This dashboard is read-only and must not be used to bypass task-next/task-open/task-submit/task-complete.",
            "The platform agent still performs creative and review judgment; this dashboard only aggregates formal route evidence.",
            "When a row is blocked, the blocking message is the next repair task.",
            "workflow-state is a navigation summary; route-audit is the formal pass/fail ledger.",
        ],
    }


__all__ = ["project_workflow_dashboard"]
