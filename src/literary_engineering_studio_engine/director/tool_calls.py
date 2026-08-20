"""Pure selection, identity, status, and summary helpers for director tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import DIRECTOR_MAX_TOOL_STEPS
from .helpers import _rel_str, _safe_jsonable, _trim_text
from .routing import _list_value, _tool_value
from .status import _compact_director_status, build_director_status


def next_director_tool_call(decision: dict[str, Any], previous_steps: list[dict[str, Any]]) -> dict[str, Any]:
    for tool_call in _tool_value(decision.get("director_tools")):
        normalized = normalize_director_tool_call(tool_call)
        if normalized.get("tool") and not tool_call_already_handled(normalized, previous_steps):
            return normalized
    return {}


def normalize_director_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    normalized = _safe_jsonable(tool_call)
    if not isinstance(normalized, dict):
        return {}
    normalized["tool"] = str(
        normalized.get("tool") or normalized.get("name") or normalized.get("action") or ""
    ).strip()
    return normalized


def tool_call_already_handled(tool_call: dict[str, Any], previous_steps: list[dict[str, Any]]) -> bool:
    key = tool_call_key(tool_call)
    return any(
        tool_call_key(step.get("tool_call", {})) == key and str(step.get("status") or "") != "skipped"
        for step in previous_steps
    )


def tool_call_key(tool_call: Any) -> tuple[str, str, str]:
    if not isinstance(tool_call, dict):
        return ("", "", "")
    return (
        str(tool_call.get("tool") or "").strip(),
        str(tool_call.get("mode") or tool_call.get("workflow") or "").strip(),
        str(tool_call.get("asset_type") or tool_call.get("type") or "").strip(),
    )


def workflow_already_executed(previous_steps: list[dict[str, Any]], workflow: str) -> bool:
    for step in previous_steps:
        if str(step.get("tool") or "") != "run_workflow":
            continue
        call = step.get("tool_call", {})
        mode = str(call.get("mode") or call.get("workflow") or "") if isinstance(call, dict) else ""
        if mode == workflow and str(step.get("status") or "") == "completed":
            return True
    return False


def director_workflow_run_id(run_id: str, previous_steps: list[dict[str, Any]], step_number: int) -> str:
    if not any(str(step.get("tool") or "") == "run_workflow" for step in previous_steps):
        return f"{run_id}-wf"
    return f"{run_id}-wf-{step_number:02d}"


def is_terminal_director_tool(tool: str) -> bool:
    return tool in {"ask_user", "write_director_report"}


def director_tool_loop_status(steps: list[dict[str, Any]], workflow_error: str) -> str:
    if workflow_error:
        return "failed"
    if not steps:
        return "completed"
    statuses = [str(step.get("status") or "") for step in steps]
    if "needs_user_direction" in statuses:
        return "needs_user_direction"
    if "failed" in statuses:
        return "failed"
    if all(status == "planned" for status in statuses):
        return "planned"
    return "completed"


def director_loop_observation(root: Path, workflow_result: Any, workflow_error: str) -> dict[str, Any]:
    observation = _compact_director_status(build_director_status(root, limit=3))
    if workflow_result is not None:
        observation["latest_workflow"] = {
            "run_id": workflow_result.run_id,
            "status": workflow_result.status,
            "state": _rel_str(workflow_result.state_path, root),
            "blocked": workflow_result.blocked,
        }
    if workflow_error:
        observation["workflow_error"] = workflow_error
    return observation


def decision_loop_summary(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": decision.get("intent", ""),
        "chosen_workflow": decision.get("chosen_workflow", ""),
        "status": decision.get("status", ""),
        "rationale": _trim_text(decision.get("rationale", ""), 600),
        "director_tools": _tool_value(decision.get("director_tools"))[:DIRECTOR_MAX_TOOL_STEPS],
        "user_visible_decisions": _list_value(decision.get("user_visible_decisions"))[:3],
    }


def tool_loop_summary(steps: list[dict[str, Any]]) -> list[str]:
    summary: list[str] = []
    for step in steps:
        tool = str(step.get("tool") or "").strip()
        status = str(step.get("status") or "").strip()
        message = _trim_text(step.get("message", ""), 180)
        if tool:
            summary.append(" | ".join(part for part in [tool, status, message] if part))
    return summary


__all__ = [
    "decision_loop_summary",
    "director_loop_observation",
    "director_tool_loop_status",
    "director_workflow_run_id",
    "is_terminal_director_tool",
    "next_director_tool_call",
    "normalize_director_tool_call",
    "tool_call_already_handled",
    "tool_call_key",
    "tool_loop_summary",
    "workflow_already_executed",
]
