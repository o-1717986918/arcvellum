"""Pure workflow dashboard projection for UI and streaming readers."""

from __future__ import annotations

from pathlib import Path

from ..task_registry import SUPPORTED_ROUTES
from .audit.task_status import project_agent_task_status, project_route_audit
from .dashboard_model import build_dashboard_payload, read_events
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
    return build_dashboard_payload(
        root,
        state_payload,
        task_payload,
        route_audits,
        read_events(root / "workflow" / "events" / "task_events.jsonl"),
        route_state_path="workflow/dashboard/route_state.json",
        task_status_path="workflow/dashboard/agent_task_status.json",
        frontend_html="workflow/dashboard/workflow_dashboard.html",
        frontend_json="workflow/dashboard/workflow_dashboard.json",
        frontend_mode="pure live projection; run workflow-dashboard to materialize portable files",
    )


__all__ = ["project_workflow_dashboard"]
