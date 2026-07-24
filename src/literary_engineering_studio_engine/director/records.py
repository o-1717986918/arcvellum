"""Persistent director run, conversation, and human-readable report artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DIRECTOR_CONVERSATION_SCHEMA
from .helpers import _now, _rel_str, _trim_text
from .routing import _conversation_memory_summary, _list_value, _tool_value
from .status import _tail_jsonl

def _director_artifacts(root: Path, agent_run_dir: Path, validation_path: Path, workflow_result: Any) -> dict[str, str]:
    artifacts = {
        "agent_decision": _rel_str(agent_run_dir / "parsed_output.json", root),
        "agent_run": _rel_str(agent_run_dir, root),
        "schema_validation": _rel_str(validation_path, root),
    }
    if workflow_result:
        artifacts.update(
            {
                "workflow_state": _rel_str(workflow_result.state_path, root),
                "workflow_log": _rel_str(workflow_result.log_path, root),
                "workflow_status": workflow_result.status,
            }
        )
    return artifacts


def _reply(decision: dict[str, Any], artifacts: dict[str, str]) -> str:
    custom = str(decision.get("conversation_reply") or "").strip()
    if custom:
        return _trim_text(custom, 1200)
    workflow = decision.get("chosen_workflow", "none")
    if decision.get("status") == "failed":
        return f"创作总监已接管本轮方向，但内部工作流失败：{artifacts.get('workflow_error', '未知错误')}。决策记录已保留。"
    if workflow == "none":
        return "创作总监已读取项目状态。本轮没有触发创作写入，你可以继续给我新的故事方向。"
    if decision.get("auto_execute"):
        return f"创作总监已把你的方向路由到 `{workflow}`，并完成内部生成/审查链路。候选与审查记录已写入项目。"
    return f"创作总监已完成路由规划，建议下一步执行 `{workflow}`。本轮未自动运行。"


def _render_report(decision: dict[str, Any], artifacts: dict[str, str]) -> str:
    lines = [
        "# Creative Director Report",
        "",
        f"- Run: `{decision.get('run_id', '')}`",
        f"- Status: `{decision.get('status', '')}`",
        f"- Provider: `{decision.get('provider', '')}`",
        f"- Intent: `{decision.get('intent', '')}`",
        f"- Chosen workflow: `{decision.get('chosen_workflow', '')}`",
        "",
        "## User Direction",
        "",
        str(decision.get("user_direction", "")),
        "",
        "## Director Rationale",
        "",
        str(decision.get("rationale", "")),
        "",
        "## Conversation Reply",
        "",
        str(decision.get("conversation_reply", "")),
        "",
        "## Director Tool Plan",
    ]
    for item in decision.get("director_tools", []):
        lines.append(f"- `{json.dumps(item, ensure_ascii=False)}`")
    lines.extend(["", "## Director Tool Loop"])
    lines.append(f"- Status: `{decision.get('tool_loop_status', '')}`")
    lines.append(f"- Steps: `{decision.get('tool_loop_step_count', 0)}`")
    if decision.get("tool_loop"):
        lines.append(f"- Loop artifact: `{decision.get('tool_loop', '')}`")
    for item in decision.get("tool_loop_summary", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Secondary Decisions",
        ]
    )
    lines.extend(f"- {item}" for item in decision.get("secondary_decisions", []))
    lines.extend(["", "## Delegated To"])
    lines.extend(f"- {item}" for item in decision.get("delegated_to", []))
    lines.extend(["", "## Constraints"])
    lines.extend(f"- {item}" for item in decision.get("constraints", []))
    lines.extend(["", "## Risks"])
    lines.extend(f"- {item}" for item in decision.get("risks", []))
    lines.extend(["", "## Artifacts"])
    lines.extend(f"- `{key}`: `{value}`" for key, value in artifacts.items())
    lines.extend(["", "## User-Level Next Direction"])
    lines.extend(f"- {item}" for item in decision.get("user_visible_decisions", []))
    lines.append("")
    return "\n".join(lines)


def _append_index(root: Path, decision: dict[str, Any], decision_path: Path, report_path: Path) -> None:
    index = root / "director" / "runs" / "index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "literary-engineering-workbench/director-run-index/v0.1",
        "run_id": decision.get("run_id", ""),
        "status": decision.get("status", ""),
        "intent": decision.get("intent", ""),
        "chosen_workflow": decision.get("chosen_workflow", ""),
        "decision": _rel_str(decision_path, root),
        "report": _rel_str(report_path, root),
        "created_at": _now(),
    }
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_conversation_turn(root: Path, decision: dict[str, Any], artifacts: dict[str, str]) -> None:
    index = root / "director" / "conversation" / "turns.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": DIRECTOR_CONVERSATION_SCHEMA,
        "run_id": decision.get("run_id", ""),
        "created_at": _now(),
        "user_direction": _trim_text(decision.get("user_direction", ""), 1200),
        "assistant_headline": _conversation_headline_for_record(decision),
        "assistant_reply": _conversation_reply_for_record(decision),
        "intent": decision.get("intent", ""),
        "chosen_workflow": decision.get("chosen_workflow", ""),
        "status": decision.get("status", ""),
        "visible_choices": [_trim_text(item, 400) for item in decision.get("user_visible_decisions", [])[:5]],
        "tool_plan": _conversation_tool_summary(decision.get("director_tools", [])),
        "tool_loop": [_trim_text(item, 400) for item in decision.get("tool_loop_summary", [])[:8]],
        "artifacts": {
            key: value
            for key, value in artifacts.items()
            if key in {
                "workflow_state",
                "workflow_status",
                "project_bootstrap",
                "schema_validation",
                "tool_loop",
                "project_direction_memory",
                "project_direction_digest",
            }
        },
    }
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_project_direction_memory(root: Path, run_id: str, direction: str, tool_call: dict[str, Any]) -> dict[str, Path]:
    memory_dir = root / "director" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    index = memory_dir / "project_direction.jsonl"
    digest = memory_dir / "project_direction.md"
    record = {
        "schema": "literary-engineering-workbench/director-project-direction/v0.1",
        "run_id": run_id,
        "created_at": _now(),
        "user_direction": _trim_text(direction, 1600),
        "summary": _trim_text(
            tool_call.get("summary")
            or tool_call.get("memory")
            or tool_call.get("reason")
            or _conversation_memory_summary(direction),
            600,
        ),
        "preferences": [_trim_text(item, 400) for item in _list_value(tool_call.get("preferences") or tool_call.get("preference"))[:8]],
        "constraints": [_trim_text(item, 400) for item in _list_value(tool_call.get("constraints") or tool_call.get("constraint"))[:8]],
        "open_questions": [_trim_text(item, 400) for item in _list_value(tool_call.get("open_questions") or tool_call.get("questions"))[:5]],
    }
    if not record["preferences"] and direction.strip():
        record["preferences"] = [_trim_text(direction, 400)]
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    recent = _tail_jsonl(index, 20)
    digest.write_text(_render_project_direction_digest(recent), encoding="utf-8")
    return {"index": index, "digest": digest}


def _render_project_direction_digest(records: list[dict[str, Any]]) -> str:
    lines = [
        "# Creative Director Project Direction Memory",
        "",
        "This file is internal project memory for the Creative Director. It records user-facing creative preferences and constraints gathered through free dialogue. It is not canon and does not directly overwrite project source files.",
        "",
    ]
    if not records:
        lines.extend(["No project direction memory yet.", ""])
        return "\n".join(lines)
    for item in records[-20:]:
        lines.append(f"## {item.get('created_at', '')}")
        lines.append("")
        lines.append(f"- Run: `{item.get('run_id', '')}`")
        lines.append(f"- Summary: {item.get('summary', '')}")
        preferences = item.get("preferences", []) if isinstance(item.get("preferences", []), list) else []
        constraints = item.get("constraints", []) if isinstance(item.get("constraints", []), list) else []
        questions = item.get("open_questions", []) if isinstance(item.get("open_questions", []), list) else []
        if preferences:
            lines.append("- Preferences:")
            lines.extend(f"  - {entry}" for entry in preferences)
        if constraints:
            lines.append("- Constraints:")
            lines.extend(f"  - {entry}" for entry in constraints)
        if questions:
            lines.append("- Open questions:")
            lines.extend(f"  - {entry}" for entry in questions)
        lines.append("")
    return "\n".join(lines)


def _conversation_headline_for_record(decision: dict[str, Any]) -> str:
    custom = str(decision.get("conversation_headline") or "").strip()
    if custom:
        return _trim_text(custom, 160)
    workflow = str(decision.get("chosen_workflow") or "none")
    if workflow == "none":
        return "项目状态确认"
    return f"创作总监建议推进 {workflow}"


def _conversation_reply_for_record(decision: dict[str, Any]) -> str:
    custom = str(decision.get("conversation_reply") or "").strip()
    if custom:
        return _trim_text(custom, 1200)
    return _trim_text(_reply(decision, {}), 1200)


def _conversation_tool_summary(value: Any) -> list[str]:
    tools = _tool_value(value)
    summary: list[str] = []
    for item in tools[:8]:
        tool = str(item.get("tool") or "").strip()
        mode = str(item.get("mode") or "").strip()
        reason = str(item.get("reason") or "").strip()
        parts = [tool]
        if mode:
            parts.append(f"mode={mode}")
        if reason:
            parts.append(reason)
        text = " | ".join(part for part in parts if part)
        if text:
            summary.append(_trim_text(text, 240))
    return summary
