"""Materialize the unified workflow dashboard for portable inspection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..agent_task_status import build_agent_task_status, build_route_audit
from ..atomic_io import atomic_write_text
from ..task_registry import SUPPORTED_ROUTES
from .dashboard_model import WORKFLOW_DASHBOARD_SCHEMA
from .dashboard_model import audit_int as _audit_int
from .dashboard_model import authority_hierarchy as _authority_hierarchy
from .dashboard_model import build_dashboard_payload
from .dashboard_model import dashboard_summary as _summary
from .dashboard_model import next_actions as _next_actions
from .dashboard_model import now as _now
from .dashboard_model import read_events as _read_events
from .dashboard_model import relative_path as _rel
from .dashboard_model import route_audit_summary as _route_audit_summary
from .dashboard_rendering import escape as _h
from .dashboard_rendering import render_html as _render_html
from .dashboard_rendering import render_markdown as _render_markdown
from .dashboard_rendering import script_json as _script_json
from .state import build_workflow_state


@dataclass(frozen=True)
class WorkflowDashboardResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    html_path: Path
    route_count: int
    blocking_count: int
    pending_task_count: int
    next_action_count: int


def build_workflow_dashboard(
    project_root: Path,
    *,
    output: Path | None = None,
    json_output: Path | None = None,
    html_output: Path | None = None,
) -> WorkflowDashboardResult:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    dashboard_dir = root / "workflow" / "dashboard"
    markdown_path = _resolve_output(root, output, dashboard_dir / "workflow_dashboard.md")
    json_path = _resolve_output(root, json_output, dashboard_dir / "workflow_dashboard.json")
    html_path = _resolve_output(root, html_output, dashboard_dir / "workflow_dashboard.html")
    for path in (markdown_path, json_path, html_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    state_payload, task_payload, route_audits = _materialized_inputs(root, dashboard_dir)
    payload = build_dashboard_payload(
        root,
        state_payload,
        task_payload,
        route_audits,
        _read_events(root / "workflow" / "events" / "task_events.jsonl"),
        route_state_path="workflow/dashboard/route_state.json",
        task_status_path="workflow/dashboard/agent_task_status.json",
        frontend_html=_rel(html_path, root),
        frontend_json=_rel(json_path, root),
        frontend_mode="static dashboard; rerun workflow-dashboard or serve the project and poll workflow/dashboard/workflow_dashboard.json for live updates",
    )
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(markdown_path, _render_markdown(payload))
    atomic_write_text(html_path, _render_html(payload))
    return _result(root, markdown_path, json_path, html_path, payload)


def _materialized_inputs(
    root: Path,
    dashboard_dir: Path,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    state = build_workflow_state(
        root,
        route="overall",
        scene_scope="dashboard",
        output=dashboard_dir / "route_state.md",
        json_output=dashboard_dir / "route_state.json",
    )
    task_status = build_agent_task_status(
        root,
        output=dashboard_dir / "agent_task_status.md",
        json_output=dashboard_dir / "agent_task_status.json",
    )
    route_audits: list[dict[str, object]] = []
    for route in sorted(SUPPORTED_ROUTES):
        audit = build_route_audit(
            root,
            route=route,
            output=dashboard_dir / f"route_audit.{route}.md",
            json_output=dashboard_dir / f"route_audit.{route}.json",
        )
        route_audits.append(_load_json(audit.json_path))
    return _load_json(state.json_path), _load_json(task_status.json_path), route_audits


def _result(
    root: Path,
    markdown_path: Path,
    json_path: Path,
    html_path: Path,
    payload: dict[str, object],
) -> WorkflowDashboardResult:
    summary = payload["summary"]
    assert isinstance(summary, dict)
    return WorkflowDashboardResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        html_path=html_path,
        route_count=int(summary["route_count"]),
        blocking_count=int(summary["blocking_count"]),
        pending_task_count=int(summary["pending_task_count"]),
        next_action_count=int(summary["next_action_count"]),
    )


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_output(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


__all__ = ["WorkflowDashboardResult", "build_workflow_dashboard"]
