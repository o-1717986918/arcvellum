"""Bounded orchestration loop for creative-director tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DIRECTOR_MAX_TOOL_STEPS, DIRECTOR_TOOL_LOOP_SCHEMA, DirectorToolLoopResult
from .helpers import _now
from .routing import _tool_value
from .tool_calls import decision_loop_summary as _decision_loop_summary
from .tool_calls import director_loop_observation as _director_loop_observation
from .tool_calls import director_tool_loop_status as _director_tool_loop_status
from .tool_calls import director_workflow_run_id as _director_workflow_run_id
from .tool_calls import is_terminal_director_tool as _is_terminal_director_tool
from .tool_calls import next_director_tool_call as _next_director_tool_call
from .tool_calls import normalize_director_tool_call as _normalize_director_tool_call
from .tool_calls import tool_call_already_handled as _tool_call_already_handled
from .tool_calls import tool_call_key as _tool_call_key
from .tool_calls import tool_loop_summary as _tool_loop_summary
from .tool_calls import workflow_already_executed as _workflow_already_executed
from .tool_execution import execute_director_tool_call as _execute_director_tool_call
from .tool_observation import deterministic_observe_decision as _deterministic_observe_decision
from .tool_observation import director_loop_user_prompt as _director_loop_user_prompt
from .tool_observation import run_director_observe_decision as _run_director_observe_decision


def _run_director_tool_loop(
    root: Path,
    *,
    run_dir: Path,
    direction: str,
    initial_decision: dict[str, Any],
    deterministic: dict[str, Any],
    provider: str,
    requested_provider: str,
    auto_execute: bool,
    agent_tasks: bool,
) -> DirectorToolLoopResult:
    loop_path = run_dir / "tool_loop.json"
    loop = _new_loop(initial_decision, auto_execute, agent_tasks)
    if not auto_execute:
        return _planned_loop(root, loop_path, loop, initial_decision)
    return _active_loop(
        root,
        loop_path,
        loop,
        run_dir=run_dir,
        direction=direction,
        initial_decision=initial_decision,
        deterministic=deterministic,
        provider=provider,
        requested_provider=requested_provider,
        agent_tasks=agent_tasks,
    )


def _new_loop(initial: dict[str, Any], auto_execute: bool, agent_tasks: bool) -> dict[str, Any]:
    return {
        "schema": DIRECTOR_TOOL_LOOP_SCHEMA,
        "run_id": initial.get("run_id", ""),
        "status": "running",
        "auto_execute": auto_execute,
        "agent_tasks": agent_tasks,
        "max_steps": DIRECTOR_MAX_TOOL_STEPS,
        "started_at": _now(),
        "ended_at": "",
        "initial_decision": _decision_loop_summary(initial),
        "steps": [],
    }


def _planned_loop(
    root: Path,
    loop_path: Path,
    loop: dict[str, Any],
    initial: dict[str, Any],
) -> DirectorToolLoopResult:
    for index, tool_call in enumerate(_tool_value(initial.get("director_tools")), start=1):
        if index > DIRECTOR_MAX_TOOL_STEPS:
            break
        normalized = _normalize_director_tool_call(tool_call)
        observation = _director_loop_observation(root, None, "")
        loop["steps"].append(
            {
                "step": index,
                "tool": normalized.get("tool", ""),
                "tool_call": normalized,
                "status": "planned",
                "started_at": _now(),
                "ended_at": _now(),
                "message": "auto_execute=false; tool call recorded but not executed.",
                "artifacts": {},
                "observation_before": observation,
                "observation_after": _director_loop_observation(root, None, ""),
            }
        )
    return _finish_loop(loop_path, loop, "planned", None, "", {})


def _active_loop(
    root: Path,
    loop_path: Path,
    loop: dict[str, Any],
    *,
    run_dir: Path,
    direction: str,
    initial_decision: dict[str, Any],
    deterministic: dict[str, Any],
    provider: str,
    requested_provider: str,
    agent_tasks: bool,
) -> DirectorToolLoopResult:
    workflow_result = None
    workflow_error = ""
    artifacts: dict[str, str] = {}
    decision = dict(initial_decision)
    for step_number in range(1, DIRECTOR_MAX_TOOL_STEPS + 1):
        tool_call = _next_director_tool_call(decision, loop["steps"])
        if not tool_call:
            break
        before = _director_loop_observation(root, workflow_result, workflow_error)
        step, result, error, step_artifacts = _execute_director_tool_call(
            root,
            run_id=str(initial_decision.get("run_id") or deterministic.get("run_id") or "director"),
            direction=direction,
            tool_call=tool_call,
            fallback_workflow=str(initial_decision.get("chosen_workflow") or deterministic.get("chosen_workflow") or "none"),
            provider=provider,
            step_number=step_number,
            previous_steps=loop["steps"],
            agent_tasks=agent_tasks,
        )
        workflow_result = result if result is not None else workflow_result
        workflow_error = error or workflow_error
        artifacts.update(step_artifacts)
        step.update(
            observation_before=before,
            observation_after=_director_loop_observation(root, workflow_result, workflow_error),
        )
        loop["steps"].append(step)
        if _stop_after_step(step):
            break
        decision = _observe_next(
            root,
            loop,
            run_dir,
            direction,
            initial_decision,
            deterministic,
            provider,
            requested_provider,
            step_number,
            step,
        )
    status = _director_tool_loop_status(loop["steps"], workflow_error)
    return _finish_loop(loop_path, loop, status, workflow_result, workflow_error, artifacts)


def _stop_after_step(step: dict[str, Any]) -> bool:
    return str(step.get("status") or "") in {"failed", "needs_user_direction"} or _is_terminal_director_tool(
        str(step.get("tool") or "")
    )


def _observe_next(
    root: Path,
    loop: dict[str, Any],
    run_dir: Path,
    direction: str,
    initial: dict[str, Any],
    deterministic: dict[str, Any],
    provider: str,
    requested_provider: str,
    step_number: int,
    step: dict[str, Any],
) -> dict[str, Any]:
    followup = _run_director_observe_decision(
        root,
        run_dir=run_dir,
        direction=direction,
        initial_decision=initial,
        previous_steps=loop["steps"],
        latest_step=step,
        deterministic=deterministic,
        provider=provider,
        requested_provider=requested_provider,
        step_number=step_number,
    )
    step["observe_decision"] = _decision_loop_summary(followup["decision"])
    step["observe_agent_run"] = followup["agent_run"]
    step["observe_validation"] = followup["validation"]
    return followup["decision"]


def _finish_loop(
    path: Path,
    loop: dict[str, Any],
    status: str,
    workflow_result: Any,
    workflow_error: str,
    artifacts: dict[str, str],
) -> DirectorToolLoopResult:
    loop["status"] = status
    loop["ended_at"] = _now()
    path.write_text(json.dumps(loop, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DirectorToolLoopResult(path, status, list(loop["steps"]), workflow_result, workflow_error, artifacts)


__all__ = []
