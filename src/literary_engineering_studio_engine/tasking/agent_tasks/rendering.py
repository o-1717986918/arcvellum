"""Markdown projections for Agent task inventory and route audit evidence."""

from __future__ import annotations


def render_status_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# 平台 Agent 任务总控面板", "",
        f"- 生成时间：{payload['generated_at']}", f"- 任务数：{summary['task_count']}",
        f"- Pending：{summary['pending_count']}", f"- Partial：{summary['partial_count']}",
        f"- Complete：{summary['complete_count']}", f"- Unknown：{summary['unknown_count']}",
        f"- 缺失预期产物：{summary['missing_expected_count']}", "",
        "## Sidecars", "", "| 状态 | Route | Task | 缺失预期产物 | 缺失 Source |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for record in payload["tasks"]:
        lines.append(f"| {record['status']} | {record['route']} | `{record['path']}` | {len(record['missing_expected_paths'])} | {len(record['missing_source_paths'])} |")
    lines.extend(["", "## 下一步", "", "- 先处理 pending / partial sidecar，再进入生成、审查、装配或发布。"])
    return "\n".join(lines).rstrip() + "\n"


def render_route_audit_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        f"# Route Audit：{summary['route']}", "",
        f"- 生成时间：{payload['generated_at']}", f"- Gate 数：{summary['gate_count']}",
        f"- Blocking：{summary['blocking_count']}", f"- Warning：{summary['warning_count']}",
        f"- 等待前序门禁：{summary.get('waiting_count', 0)}", f"- 未完成 sidecar：{summary['pending_task_count']}",
        "", "## Gates", "", "| 状态 | 级别 | Gate | 说明 |", "| --- | --- | --- | --- |",
    ]
    scene_scope = summary.get("scene_scope") if isinstance(summary.get("scene_scope"), dict) else {}
    if scene_scope:
        lines[7:7] = [f"- 场景审计范围：已开始 {scene_scope.get('started_scene_count', 0)} / 总数 {scene_scope.get('total_scene_count', 0)}；未开始计划场景 {scene_scope.get('planned_scene_count', 0)} 不计为失败。"]
    for gate in payload["gates"]:
        lines.append(f"| {gate['status']} | {gate['severity']} | {gate['key']} | {gate['message']} |")
    lines.extend(["", "## Sidecar Summary", "", "| 状态 | Route | Task |", "| --- | --- | --- |"])
    for record in payload["tasks"]:
        lines.append(f"| {record['status']} | {record['route']} | `{record['path']}` |")
    return "\n".join(lines).rstrip() + "\n"
