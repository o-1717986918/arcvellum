"""Markdown and portable HTML rendering for materialized dashboards."""

from __future__ import annotations

import html
import json


def render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"] if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Workflow Dashboard", "", f"- 生成时间：{payload.get('generated_at', '')}",
        f"- Ready：{summary.get('ready_count', 0)}", f"- State blocked：{summary.get('state_blocked_count', 0)}",
        f"- Route blocking gates：{summary.get('blocking_count', 0)}",
        f"- Pending sidecars：{summary.get('pending_task_count', 0)}",
        f"- Missing expected artifacts：{summary.get('missing_expected_count', 0)}", "", "## Authority Hierarchy", "",
    ]
    for item in payload.get("authority_hierarchy", []):
        if isinstance(item, dict):
            lines.append(f"- **{item.get('level', '')}**：{item.get('meaning', '')}")
    lines.extend(["", "## Route Audits", "", "| Route | Blocking | Warning | Pending tasks |", "| --- | ---: | ---: | ---: |"])
    for audit in payload.get("route_audits", []):
        if isinstance(audit, dict):
            lines.append(
                f"| {audit.get('route', '')} | {audit.get('blocking_count', 0)} | "
                f"{audit.get('warning_count', 0)} | {audit.get('pending_task_count', 0)} |"
            )
    lines.extend(["", "## Next Actions", "", "| Route | Target | Current step | Next action |", "| --- | --- | --- | --- |"])
    for action in payload.get("next_actions", []):
        if isinstance(action, dict):
            lines.append(
                f"| {action.get('route', '')} | {action.get('target', '')} | "
                f"{action.get('current_step', '')} | {action.get('next_action', '')} |"
            )
    frontend = payload.get("frontend") if isinstance(payload.get("frontend"), dict) else {}
    lines.extend(
        [
            "", "## Frontend", "", f"- HTML：`{frontend.get('html', '')}`", f"- JSON：`{frontend.get('json', '')}`",
            "- 说明：这是只读总控面板。正式推进仍必须走 `task-next -> task-open -> task-submit -> task-complete`。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_html(payload: dict[str, object]) -> str:
    summary = payload["summary"] if isinstance(payload.get("summary"), dict) else {}
    route_rows = "".join(_route_row(item) for item in payload.get("route_audits", []) if isinstance(item, dict))
    action_rows = "".join(_action_row(item) for item in payload.get("next_actions", []) if isinstance(item, dict))
    authority = "".join(
        f"<li><strong>{escape(item.get('level', ''))}</strong>：{escape(item.get('meaning', ''))}</li>"
        for item in payload.get("authority_hierarchy", [])
        if isinstance(item, dict)
    )
    data = script_json(payload)
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
  <div class="muted">只读总控面板。生成时间：{escape(payload.get('generated_at', ''))}。页面每 20 秒刷新一次；重新运行 <code>workflow-dashboard</code> 可更新数据。</div>
  <div class="grid">
    <div class="metric">Ready<strong>{escape(summary.get('ready_count', 0))}</strong></div>
    <div class="metric">State blocked<strong>{escape(summary.get('state_blocked_count', 0))}</strong></div>
    <div class="metric">Route blocking gates<strong>{escape(summary.get('blocking_count', 0))}</strong></div>
    <div class="metric">Pending sidecars<strong>{escape(summary.get('pending_task_count', 0))}</strong></div>
    <div class="metric">Missing expected<strong>{escape(summary.get('missing_expected_count', 0))}</strong></div>
  </div>
  <section>
    <h2>Authority Hierarchy</h2>
    <ul>{authority}</ul>
  </section>
  <section>
    <h2>Route Audits</h2>
    <table>
      <thead><tr><th>Route</th><th>Blocking</th><th>Warning</th><th>Pending tasks</th></tr></thead>
      <tbody>{route_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Next Actions</h2>
    <table>
      <thead><tr><th>Route</th><th>Target</th><th>Current step</th><th>Next action</th></tr></thead>
      <tbody>{action_rows or '<tr><td colspan="4">No pending next action.</td></tr>'}</tbody>
    </table>
  </section>
  <script id="workflow-dashboard-data" type="application/json">{data}</script>
</main>
</body>
</html>
"""


def _route_row(audit: dict[str, object]) -> str:
    return (
        "<tr>" f"<td>{escape(audit.get('route', ''))}</td>"
        f"<td>{escape(audit.get('blocking_count', 0))}</td>"
        f"<td>{escape(audit.get('warning_count', 0))}</td>"
        f"<td>{escape(audit.get('pending_task_count', 0))}</td>" "</tr>"
    )


def _action_row(action: dict[str, object]) -> str:
    return (
        "<tr>" f"<td>{escape(action.get('route', ''))}</td>" f"<td>{escape(action.get('target', ''))}</td>"
        f"<td>{escape(action.get('current_step', ''))}</td>" f"<td>{escape(action.get('next_action', ''))}</td>" "</tr>"
    )


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def script_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
