"""Unified workflow dashboard for CLI-mediated platform-agent routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import json
from pathlib import Path

from .agent_task_status import build_agent_task_status, build_route_audit
from .atomic_io import atomic_write_text
from .task_registry import SUPPORTED_ROUTES
from .workflow_state import build_workflow_state


WORKFLOW_DASHBOARD_SCHEMA = "literary-engineering-workbench/workflow-dashboard/v0.1"


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
    """Build a cross-route cockpit without advancing any formal workflow state."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    dashboard_dir = root / "workflow" / "dashboard"
    markdown_path = _resolve_output(root, output, dashboard_dir / "workflow_dashboard.md")
    json_path = _resolve_output(root, json_output, dashboard_dir / "workflow_dashboard.json")
    html_path = _resolve_output(root, html_output, dashboard_dir / "workflow_dashboard.html")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)

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
    route_audits = []
    for route in sorted(SUPPORTED_ROUTES):
        audit = build_route_audit(
            root,
            route=route,
            output=dashboard_dir / f"route_audit.{route}.md",
            json_output=dashboard_dir / f"route_audit.{route}.json",
        )
        route_audits.append(_load_json(audit.json_path))
    state_payload = _load_json(state.json_path)
    task_payload = _load_json(task_status.json_path)
    events = _read_events(root / "workflow" / "events" / "task_events.jsonl")
    next_actions = _next_actions(state_payload, route_audits)
    summary = _summary(state_payload, task_payload, route_audits, next_actions)
    payload = {
        "schema": WORKFLOW_DASHBOARD_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "authority_hierarchy": _authority_hierarchy(),
        "route_state": {
            "path": _rel(state.json_path, root),
            "summary": state_payload.get("summary", {}),
        },
        "agent_task_status": {
            "path": _rel(task_status.json_path, root),
            "summary": task_payload.get("summary", {}),
        },
        "route_audits": [_route_audit_summary(root, audit) for audit in route_audits],
        "next_actions": next_actions,
        "recent_events": events[-25:],
        "frontend": {
            "html": _rel(html_path, root),
            "json": _rel(json_path, root),
            "mode": "static dashboard; rerun workflow-dashboard or serve the project and poll workflow/dashboard/workflow_dashboard.json for live updates",
        },
        "rules": [
            "This dashboard is read-only and must not be used to bypass task-next/task-open/task-submit/task-complete.",
            "The platform agent still performs creative and review judgment; this dashboard only aggregates formal route evidence.",
            "When a row is blocked, the blocking message is the next repair task.",
            "workflow-state is a navigation summary; route-audit is the formal pass/fail ledger.",
        ],
    }
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(markdown_path, _render_markdown(payload))
    atomic_write_text(html_path, _render_html(payload))
    return WorkflowDashboardResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        html_path=html_path,
        route_count=len(route_audits),
        blocking_count=int(summary["blocking_count"]),
        pending_task_count=int(summary["pending_task_count"]),
        next_action_count=int(summary["next_action_count"]),
    )


def _summary(
    state_payload: dict[str, object],
    task_payload: dict[str, object],
    route_audits: list[dict[str, object]],
    next_actions: list[dict[str, object]],
) -> dict[str, object]:
    state_summary = state_payload.get("summary") if isinstance(state_payload.get("summary"), dict) else {}
    task_summary = task_payload.get("summary") if isinstance(task_payload.get("summary"), dict) else {}
    return {
        "route_count": len(route_audits),
        "ready_count": int(state_summary.get("ready_count") or 0),
        "state_blocked_count": int(state_summary.get("blocked_count") or 0),
        "next_action_count": len(next_actions),
        "sidecar_task_count": int(task_summary.get("task_count") or 0),
        "pending_task_count": int(task_summary.get("pending_count") or 0)
        + int(task_summary.get("partial_count") or 0)
        + int(task_summary.get("unknown_count") or 0),
        "missing_expected_count": int(task_summary.get("missing_expected_count") or 0),
        "blocking_count": sum(_audit_int(audit, "blocking_count") for audit in route_audits),
        "warning_count": sum(_audit_int(audit, "warning_count") for audit in route_audits),
    }


def _route_audit_summary(root: Path, payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), list) else []
    return {
        "route": str(summary.get("route") or ""),
        "path": _rel(root / "workflow" / "dashboard" / f"route_audit.{summary.get('route', 'overall')}.json", root),
        "gate_count": int(summary.get("gate_count") or 0),
        "blocking_count": int(summary.get("blocking_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "pending_task_count": int(summary.get("pending_task_count") or 0),
        "top_blocking_gates": [
            {
                "key": str(gate.get("key") or ""),
                "message": str(gate.get("message") or ""),
            }
            for gate in gates
            if isinstance(gate, dict) and gate.get("severity") == "blocking" and gate.get("status") != "pass"
        ][:5],
    }


def _next_actions(state_payload: dict[str, object], route_audits: list[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for route_key, items in (
        ("scene-development", state_payload.get("scenes")),
        ("source-ingest", state_payload.get("source_ingests")),
        ("style-engineering", state_payload.get("styles")),
        ("character-and-world-assets", state_payload.get("assets")),
        ("review-and-audit", state_payload.get("audits")),
        ("export-and-release", state_payload.get("exports")),
    ):
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            action = str(item.get("next_action") or "").strip()
            if not action:
                continue
            actions.append(
                {
                    "route": route_key,
                    "target": str(item.get("scene_id") or item.get("target_id") or item.get("work_id") or item.get("candidate_id") or item.get("chapter_id") or ""),
                    "current_step": str(item.get("current_step") or ""),
                    "next_action": action,
                }
            )
    longform = state_payload.get("longform") if isinstance(state_payload.get("longform"), dict) else {}
    if longform.get("next_action"):
        actions.append(
            {
                "route": "longform-planning",
                "target": "longform",
                "current_step": str(longform.get("current_step") or ""),
                "next_action": str(longform.get("next_action") or ""),
            }
        )
    for audit in route_audits:
        summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
        route = str(summary.get("route") or "")
        gates = audit.get("gates") if isinstance(audit.get("gates"), list) else []
        for gate in gates:
            if not isinstance(gate, dict):
                continue
            if gate.get("severity") == "blocking" and gate.get("status") != "pass":
                actions.append(
                    {
                        "route": route,
                        "target": str(gate.get("key") or ""),
                        "current_step": "route-audit",
                        "next_action": str(gate.get("message") or ""),
                    }
                )
    deduped: list[dict[str, object]] = []
    seen = set()
    for action in actions:
        key = (action["route"], action["target"], action["current_step"], action["next_action"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped[:50]


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"] if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Workflow Dashboard",
        "",
        f"- 生成时间：{payload.get('generated_at', '')}",
        f"- Ready：{summary.get('ready_count', 0)}",
        f"- State blocked：{summary.get('state_blocked_count', 0)}",
        f"- Route blocking gates：{summary.get('blocking_count', 0)}",
        f"- Pending sidecars：{summary.get('pending_task_count', 0)}",
        f"- Missing expected artifacts：{summary.get('missing_expected_count', 0)}",
        "",
        "## Authority Hierarchy",
        "",
    ]
    for item in payload.get("authority_hierarchy", []):
        if isinstance(item, dict):
            lines.append(f"- **{item.get('level', '')}**：{item.get('meaning', '')}")
    lines.extend(
        [
        "",
        "## Route Audits",
        "",
        "| Route | Blocking | Warning | Pending tasks |",
        "| --- | ---: | ---: | ---: |",
        ]
    )
    for audit in payload.get("route_audits", []):
        if not isinstance(audit, dict):
            continue
        lines.append(
            f"| {audit.get('route', '')} | {audit.get('blocking_count', 0)} | {audit.get('warning_count', 0)} | {audit.get('pending_task_count', 0)} |"
        )
    lines.extend(["", "## Next Actions", "", "| Route | Target | Current step | Next action |", "| --- | --- | --- | --- |"])
    for action in payload.get("next_actions", []):
        if not isinstance(action, dict):
            continue
        lines.append(
            f"| {action.get('route', '')} | {action.get('target', '')} | {action.get('current_step', '')} | {action.get('next_action', '')} |"
        )
    lines.extend(
        [
            "",
            "## Frontend",
            "",
            f"- HTML：`{payload.get('frontend', {}).get('html', '') if isinstance(payload.get('frontend'), dict) else ''}`",
            f"- JSON：`{payload.get('frontend', {}).get('json', '') if isinstance(payload.get('frontend'), dict) else ''}`",
            "- 说明：这是只读总控面板。正式推进仍必须走 `task-next -> task-open -> task-submit -> task-complete`。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_html(payload: dict[str, object]) -> str:
    summary = payload["summary"] if isinstance(payload.get("summary"), dict) else {}
    route_rows = []
    for audit in payload.get("route_audits", []):
        if not isinstance(audit, dict):
            continue
        route_rows.append(
            "<tr>"
            f"<td>{_h(audit.get('route', ''))}</td>"
            f"<td>{_h(audit.get('blocking_count', 0))}</td>"
            f"<td>{_h(audit.get('warning_count', 0))}</td>"
            f"<td>{_h(audit.get('pending_task_count', 0))}</td>"
            "</tr>"
        )
    action_rows = []
    for action in payload.get("next_actions", []):
        if not isinstance(action, dict):
            continue
        action_rows.append(
            "<tr>"
            f"<td>{_h(action.get('route', ''))}</td>"
            f"<td>{_h(action.get('target', ''))}</td>"
            f"<td>{_h(action.get('current_step', ''))}</td>"
            f"<td>{_h(action.get('next_action', ''))}</td>"
            "</tr>"
        )
    data = _script_json(payload)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="20">
  <title>Literary Engineering Workflow Dashboard</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Arial, "Microsoft YaHei", sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #1f2933; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .muted {{ color: #667085; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 20px 0; }}
    .metric {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; }}
    .metric strong {{ display: block; font-size: 28px; margin-top: 6px; }}
    section {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; margin-top: 14px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e6e9ef; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #475467; font-weight: 600; }}
    code {{ background: #eef2f7; border-radius: 4px; padding: 2px 4px; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #111827; color: #e5e7eb; }}
      .metric, section {{ background: #1f2937; border-color: #374151; }}
      th, td {{ border-color: #374151; }}
      .muted {{ color: #9ca3af; }}
      code {{ background: #374151; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Literary Engineering Workflow Dashboard</h1>
  <div class="muted">只读总控面板。生成时间：{_h(payload.get('generated_at', ''))}。页面每 20 秒刷新一次；重新运行 <code>workflow-dashboard</code> 可更新数据。</div>
  <div class="grid">
    <div class="metric">Ready<strong>{_h(summary.get('ready_count', 0))}</strong></div>
    <div class="metric">State blocked<strong>{_h(summary.get('state_blocked_count', 0))}</strong></div>
    <div class="metric">Route blocking gates<strong>{_h(summary.get('blocking_count', 0))}</strong></div>
    <div class="metric">Pending sidecars<strong>{_h(summary.get('pending_task_count', 0))}</strong></div>
    <div class="metric">Missing expected<strong>{_h(summary.get('missing_expected_count', 0))}</strong></div>
  </div>
  <section>
    <h2>Authority Hierarchy</h2>
    <ul>{''.join(f"<li><strong>{_h(item.get('level', ''))}</strong>：{_h(item.get('meaning', ''))}</li>" for item in payload.get('authority_hierarchy', []) if isinstance(item, dict))}</ul>
  </section>
  <section>
    <h2>Route Audits</h2>
    <table>
      <thead><tr><th>Route</th><th>Blocking</th><th>Warning</th><th>Pending tasks</th></tr></thead>
      <tbody>{''.join(route_rows)}</tbody>
    </table>
  </section>
  <section>
    <h2>Next Actions</h2>
    <table>
      <thead><tr><th>Route</th><th>Target</th><th>Current step</th><th>Next action</th></tr></thead>
      <tbody>{''.join(action_rows) or '<tr><td colspan="4">No pending next action.</td></tr>'}</tbody>
    </table>
  </section>
  <script id="workflow-dashboard-data" type="application/json">{data}</script>
</main>
</body>
</html>
"""


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {
                "schema": "literary-engineering-workbench/workflow-event/v1",
                "event_type": "invalid",
                "task_id": "",
                "created_at": "",
                "data": {"raw": line},
            }
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _audit_int(payload: dict[str, object], key: str) -> int:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return int(summary.get(key) or 0)


def _authority_hierarchy() -> list[dict[str, str]]:
    return [
        {"level": "task-next", "meaning": "唯一推荐入口：选择当前 route 的下一项正式任务。"},
        {"level": "task-open", "meaning": "执行包入口：平台 Agent 读取此包和 source artifacts 后再动手。"},
        {"level": "task-submit / task-complete", "meaning": "产物落地与完成标记，未完成不得前进。"},
        {"level": "route-audit", "meaning": "正式门禁证据：判断 route 是否真的通过。"},
        {"level": "workflow-dashboard", "meaning": "只读驾驶舱：方便观察，不推进状态。"},
        {"level": "workflow-state", "meaning": "导航摘要：提示当前步骤，不替代 route-audit。"},
        {"level": "low-level commands", "meaning": "内部执行命令：除 task package 指定外，不应由宿主 Agent 自行挑选。"},
    ]


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


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


def _script_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
