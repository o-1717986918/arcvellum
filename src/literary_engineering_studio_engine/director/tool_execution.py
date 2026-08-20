"""Whitelisted tool execution for the creative director loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..asset_workshop import create_asset_candidate, list_asset_candidates, review_candidate_asset
from ..workflow_runner import run_workflow
from .contracts import DIRECTOR_ALLOWED_TOOLS
from .helpers import _now, _positive_int, _rel_str
from .records import _append_project_direction_memory
from .routing import _safe_workflow
from .status import _compact_director_status, build_director_status
from .tool_calls import director_workflow_run_id, normalize_director_tool_call, workflow_already_executed


@dataclass(frozen=True)
class ToolExecutionRequest:
    root: Path
    run_id: str
    direction: str
    fallback_workflow: str
    provider: str
    step_number: int
    previous_steps: list[dict[str, Any]]
    agent_tasks: bool


@dataclass(frozen=True)
class ToolOutcome:
    workflow_result: Any = None
    workflow_error: str = ""
    artifacts: dict[str, str] | None = None


ToolHandler = Callable[[ToolExecutionRequest, dict[str, Any], dict[str, Any]], ToolOutcome]


def execute_director_tool_call(
    root: Path,
    *,
    run_id: str,
    direction: str,
    tool_call: dict[str, Any],
    fallback_workflow: str,
    provider: str,
    step_number: int,
    previous_steps: list[dict[str, Any]],
    agent_tasks: bool,
) -> tuple[dict[str, Any], Any, str, dict[str, str]]:
    normalized = normalize_director_tool_call(tool_call)
    step = _running_step(step_number, normalized)
    request = ToolExecutionRequest(
        root,
        run_id,
        direction,
        fallback_workflow,
        provider,
        step_number,
        previous_steps,
        agent_tasks,
    )
    outcome = ToolOutcome(artifacts={})
    try:
        handler = TOOL_HANDLERS.get(str(normalized.get("tool") or ""))
        if handler is None or str(normalized.get("tool") or "") not in DIRECTOR_ALLOWED_TOOLS:
            step.update(status="skipped", message=f"unsupported director tool: {normalized.get('tool', '')}")
        else:
            outcome = handler(request, normalized, step)
    except Exception as exc:
        step.update(status="failed", error=str(exc), message=str(exc))
        outcome = ToolOutcome(workflow_error=str(exc), artifacts={})
    step["ended_at"] = _now()
    return step, outcome.workflow_result, outcome.workflow_error, dict(outcome.artifacts or {})


def _running_step(step_number: int, call: dict[str, Any]) -> dict[str, Any]:
    return {
        "step": step_number,
        "tool": str(call.get("tool") or "").strip(),
        "tool_call": call,
        "status": "running",
        "started_at": _now(),
        "ended_at": "",
        "message": "",
        "artifacts": {},
        "error": "",
    }


def _init_project(_request: ToolExecutionRequest, _call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    step.update(status="skipped", message="project already exists for this director turn; bootstrap is handled before the loop.")
    return ToolOutcome(artifacts={})


def _summarize(request: ToolExecutionRequest, _call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    step.update(
        status="completed",
        message="project status observed.",
        summary=_compact_director_status(build_director_status(request.root, limit=5)),
    )
    return ToolOutcome(artifacts={})


def _record_direction(request: ToolExecutionRequest, call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    paths = _append_project_direction_memory(request.root, request.run_id, request.direction, call)
    artifacts = {
        "project_direction_memory": _rel_str(paths["index"], request.root),
        "project_direction_digest": _rel_str(paths["digest"], request.root),
    }
    step.update(status="completed", message="project direction memory recorded.", artifacts=dict(artifacts))
    return ToolOutcome(artifacts=artifacts)


def _ask_user(_request: ToolExecutionRequest, call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    message = str(call.get("question") or call.get("reason") or "needs user direction").strip()
    step.update(status="needs_user_direction", message=message)
    return ToolOutcome(artifacts={})


def _write_report(_request: ToolExecutionRequest, _call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    step.update(status="completed", message="final director report will be written after the loop.")
    return ToolOutcome(artifacts={})


def _run_workflow(request: ToolExecutionRequest, call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    workflow = _safe_workflow(call.get("mode") or call.get("workflow") or request.fallback_workflow, request.fallback_workflow)
    if workflow == "none":
        step.update(status="skipped", message="no workflow selected.")
        return ToolOutcome(artifacts={})
    if workflow_already_executed(request.previous_steps, workflow):
        step.update(status="skipped", message=f"workflow already executed in this loop: {workflow}")
        return ToolOutcome(artifacts={})
    result = run_workflow(
        request.root,
        mode=workflow,
        scene=Path("scenes/scene_0001.yaml"),
        generate_candidate=workflow == "scene-loop",
        agent_review=True,
        agent_tasks=request.agent_tasks,
        provider=request.provider,
        run_id=director_workflow_run_id(request.run_id, request.previous_steps, request.step_number),
        brief=request.direction,
    )
    artifacts = {
        "workflow_state": _rel_str(result.state_path, request.root),
        "workflow_log": _rel_str(result.log_path, request.root),
        "workflow_status": result.status,
    }
    failed = result.status == "failed"
    step.update(
        status="failed" if failed else "completed",
        message=f"workflow `{workflow}` finished with status `{result.status}`.",
        artifacts=dict(artifacts),
    )
    return ToolOutcome(result, f"workflow `{workflow}` failed" if failed else "", artifacts)


def _create_candidate(request: ToolExecutionRequest, call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    asset_type = str(call.get("asset_type") or call.get("type") or "").strip()
    if not asset_type:
        step.update(status="skipped", message="asset_type is required for create_asset_candidate.")
        return ToolOutcome(artifacts={})
    result = create_asset_candidate(
        request.root,
        asset_type=asset_type,
        brief=str(call.get("brief") or call.get("reason") or request.direction),
        target_id=str(call.get("target_id") or ""),
        provider=request.provider,
    )
    artifacts = {
        "candidate": _rel_str(result.candidate_path, request.root),
        "candidate_report": _rel_str(result.report_path, request.root),
        "candidate_validation": _rel_str(result.validation_path, request.root),
    }
    step.update(
        status="completed" if result.status == "pass" else "failed",
        message=f"{result.asset_type} candidate `{result.candidate_id}` created with validation `{result.status}`.",
        artifacts=dict(artifacts),
    )
    return ToolOutcome(artifacts=artifacts)


def _review_candidates(request: ToolExecutionRequest, call: dict[str, Any], step: dict[str, Any]) -> ToolOutcome:
    limit = _positive_int(call.get("limit"), 3)
    asset_type = str(call.get("asset_type") or call.get("type") or "")
    candidates = list_asset_candidates(request.root, asset_type=asset_type)[:limit]
    if not candidates:
        step.update(status="skipped", message="no candidate assets found to review.")
        return ToolOutcome(artifacts={})
    reviewed = _review_candidate_paths(request, candidates)
    artifacts = {"review_count": str(len(reviewed))}
    if reviewed:
        artifacts["latest_candidate_review"] = reviewed[-1]
    step.update(
        status="completed" if reviewed else "skipped",
        message=f"reviewed {len(reviewed)} candidate asset(s).",
        artifacts=dict(artifacts),
    )
    return ToolOutcome(artifacts=artifacts)


def _review_candidate_paths(request: ToolExecutionRequest, candidates: list[dict[str, object]]) -> list[str]:
    reviewed: list[str] = []
    for candidate in candidates:
        path = str(candidate.get("path") or "")
        if path:
            result = review_candidate_asset(request.root, path, provider=request.provider)
            reviewed.append(_rel_str(result.json_path, request.root))
    return reviewed


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "init_project": _init_project,
    "summarize_project_status": _summarize,
    "record_project_direction": _record_direction,
    "ask_user": _ask_user,
    "write_director_report": _write_report,
    "run_workflow": _run_workflow,
    "create_asset_candidate": _create_candidate,
    "review_candidates": _review_candidates,
}


__all__ = ["execute_director_tool_call"]
