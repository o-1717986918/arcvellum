"""Stable public facade for Agent task inventory and route audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from ...agent_task_inventory import AgentTaskRecord, _path_exists, scan_agent_tasks
from ...agent_task_inventory import summarize_records as _summary
from ...agent_task_rendering import render_route_audit_markdown as _render_route_audit_markdown
from ...agent_task_rendering import render_status_markdown as _render_status_markdown
from ...route_audit import build_route_gates as _route_gates
from ...route_audit import scene_audit_scope as _scene_audit_scope
from ...route_audit_common import _normalize_route, _now, _resolve_output


@dataclass(frozen=True)
class AgentTaskStatusResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    task_count: int
    pending_count: int
    partial_count: int
    complete_count: int
    missing_expected_count: int


@dataclass(frozen=True)
class RouteAuditResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    route: str
    gate_count: int
    blocking_count: int
    warning_count: int
    pending_task_count: int


def build_agent_task_status(
    project_root: Path,
    *,
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentTaskStatusResult:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    records = scan_agent_tasks(root)
    summary = _summary(records)
    markdown_path = _resolve_output(root, output, "workflow", "agent_task_status.md")
    json_path = _resolve_output(root, json_output, "workflow", "agent_task_status.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/agent-task-status/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "tasks": [asdict(record) for record in records],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_status_markdown(payload), encoding="utf-8")
    return AgentTaskStatusResult(
        project_root=root, markdown_path=markdown_path, json_path=json_path,
        task_count=summary["task_count"], pending_count=summary["pending_count"],
        partial_count=summary["partial_count"], complete_count=summary["complete_count"],
        missing_expected_count=summary["missing_expected_count"],
    )


def build_route_audit(
    project_root: Path,
    *,
    route: str = "",
    output: Path | None = None,
    json_output: Path | None = None,
) -> RouteAuditResult:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    records = scan_agent_tasks(root)
    normalized_route = _normalize_route(route)
    gates = _route_gates(root, normalized_route, records)
    scene_scope = _scene_audit_scope(root) if normalized_route == "scene-development" else {}
    summary = {
        "route": normalized_route or "overall",
        "gate_count": len(gates),
        "blocking_count": sum(1 for gate in gates if gate["severity"] == "blocking"),
        "warning_count": sum(1 for gate in gates if gate["severity"] == "warning"),
        "waiting_count": sum(1 for gate in gates if gate["status"] == "waiting"),
        "pass_count": sum(1 for gate in gates if gate["status"] == "pass"),
        "pending_task_count": sum(1 for record in records if record.status in {"pending", "partial", "unknown"}),
        "missing_expected_count": sum(len(record.missing_expected_paths) for record in records),
    }
    if scene_scope:
        summary["scene_scope"] = scene_scope
    markdown_path = _resolve_output(root, output, "workflow", "route_audit.md")
    json_path = _resolve_output(root, json_output, "workflow", "route_audit.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/route-audit/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "gates": gates,
        "tasks": [asdict(record) for record in records],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_route_audit_markdown(payload), encoding="utf-8")
    return RouteAuditResult(
        project_root=root, markdown_path=markdown_path, json_path=json_path, route=summary["route"],
        gate_count=summary["gate_count"], blocking_count=summary["blocking_count"],
        warning_count=summary["warning_count"], pending_task_count=summary["pending_task_count"],
    )
