"""Bounded tool-observe-decide loop for the creative director."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agent_provider import run_agent_task
from ..agent_schema import validate_agent_run
from ..asset_workshop import create_asset_candidate, list_asset_candidates, review_candidate_asset
from ..workflow_runner import run_workflow
from .contracts import DIRECTOR_ALLOWED_TOOLS, DIRECTOR_MAX_TOOL_STEPS, DIRECTOR_SCHEMA, DIRECTOR_SCHEMA_VALUE, DIRECTOR_TOOL_LOOP_SCHEMA, DirectorToolLoopResult
from .helpers import _now, _positive_int, _rel_str, _safe_jsonable, _trim_text
from .prompts import _template
from .records import _append_project_direction_memory
from .routing import _list_value, _normalize_director_decision, _safe_workflow, _tool_value, _usable_decision
from .status import _compact_director_status, build_director_status

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
    started_at = _now()
    loop: dict[str, Any] = {
        "schema": DIRECTOR_TOOL_LOOP_SCHEMA,
        "run_id": initial_decision.get("run_id", ""),
        "status": "running",
        "auto_execute": auto_execute,
        "agent_tasks": agent_tasks,
        "max_steps": DIRECTOR_MAX_TOOL_STEPS,
        "started_at": started_at,
        "ended_at": "",
        "initial_decision": _decision_loop_summary(initial_decision),
        "steps": [],
    }
    workflow_result = None
    workflow_error = ""
    artifacts: dict[str, str] = {}

    if not auto_execute:
        for index, tool_call in enumerate(_tool_value(initial_decision.get("director_tools")), start=1):
            if index > DIRECTOR_MAX_TOOL_STEPS:
                break
            normalized = _normalize_director_tool_call(tool_call)
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
                    "observation_before": _director_loop_observation(root, None, ""),
                    "observation_after": _director_loop_observation(root, None, ""),
                }
            )
        loop["status"] = "planned"
        loop["ended_at"] = _now()
        loop_path.write_text(json.dumps(loop, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return DirectorToolLoopResult(loop_path, "planned", list(loop["steps"]), None, "", {})

    current_decision = dict(initial_decision)
    for step_number in range(1, DIRECTOR_MAX_TOOL_STEPS + 1):
        tool_call = _next_director_tool_call(current_decision, loop["steps"])
        if not tool_call:
            break
        observation_before = _director_loop_observation(root, workflow_result, workflow_error)
        step, step_workflow_result, step_error, step_artifacts = _execute_director_tool_call(
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
        if step_workflow_result is not None:
            workflow_result = step_workflow_result
        if step_error:
            workflow_error = step_error
        artifacts.update(step_artifacts)
        step["observation_before"] = observation_before
        step["observation_after"] = _director_loop_observation(root, workflow_result, workflow_error)
        loop["steps"].append(step)

        if step["status"] in {"failed", "needs_user_direction"}:
            break
        if _is_terminal_director_tool(str(step.get("tool") or "")):
            break

        followup = _run_director_observe_decision(
            root,
            run_dir=run_dir,
            direction=direction,
            initial_decision=initial_decision,
            previous_steps=loop["steps"],
            latest_step=step,
            deterministic=deterministic,
            provider=provider,
            requested_provider=requested_provider,
            step_number=step_number,
        )
        loop["steps"][-1]["observe_decision"] = _decision_loop_summary(followup["decision"])
        loop["steps"][-1]["observe_agent_run"] = followup["agent_run"]
        loop["steps"][-1]["observe_validation"] = followup["validation"]
        current_decision = followup["decision"]

    loop["status"] = _director_tool_loop_status(loop["steps"], workflow_error)
    loop["ended_at"] = _now()
    loop_path.write_text(json.dumps(loop, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return DirectorToolLoopResult(loop_path, str(loop["status"]), list(loop["steps"]), workflow_result, workflow_error, artifacts)


def _execute_director_tool_call(
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
    started_at = _now()
    normalized = _normalize_director_tool_call(tool_call)
    tool = str(normalized.get("tool") or "").strip()
    step: dict[str, Any] = {
        "step": step_number,
        "tool": tool,
        "tool_call": normalized,
        "status": "running",
        "started_at": started_at,
        "ended_at": "",
        "message": "",
        "artifacts": {},
        "error": "",
    }
    workflow_result = None
    workflow_error = ""
    artifacts: dict[str, str] = {}

    try:
        if tool not in DIRECTOR_ALLOWED_TOOLS:
            step["status"] = "skipped"
            step["message"] = f"unsupported director tool: {tool}"
        elif tool == "init_project":
            step["status"] = "skipped"
            step["message"] = "project already exists for this director turn; bootstrap is handled before the loop."
        elif tool == "summarize_project_status":
            status = build_director_status(root, limit=5)
            step["status"] = "completed"
            step["message"] = "project status observed."
            step["summary"] = _compact_director_status(status)
        elif tool == "record_project_direction":
            memory_paths = _append_project_direction_memory(root, run_id, direction, normalized)
            artifacts = {
                "project_direction_memory": _rel_str(memory_paths["index"], root),
                "project_direction_digest": _rel_str(memory_paths["digest"], root),
            }
            step["status"] = "completed"
            step["message"] = "project direction memory recorded."
            step["artifacts"] = dict(artifacts)
        elif tool == "ask_user":
            step["status"] = "needs_user_direction"
            step["message"] = str(normalized.get("question") or normalized.get("reason") or "needs user direction").strip()
        elif tool == "write_director_report":
            step["status"] = "completed"
            step["message"] = "final director report will be written after the loop."
        elif tool == "run_workflow":
            workflow = _safe_workflow(normalized.get("mode") or normalized.get("workflow") or fallback_workflow, fallback_workflow)
            if workflow == "none":
                step["status"] = "skipped"
                step["message"] = "no workflow selected."
            elif _workflow_already_executed(previous_steps, workflow):
                step["status"] = "skipped"
                step["message"] = f"workflow already executed in this loop: {workflow}"
            else:
                workflow_run_id = _director_workflow_run_id(run_id, previous_steps, step_number)
                result = run_workflow(
                    root,
                    mode=workflow,
                    scene=Path("scenes/scene_0001.yaml"),
                    generate_candidate=workflow == "scene-loop",
                    agent_review=True,
                    agent_tasks=agent_tasks,
                    provider=provider,
                    run_id=workflow_run_id,
                    brief=direction,
                )
                workflow_result = result
                artifacts = {
                    "workflow_state": _rel_str(result.state_path, root),
                    "workflow_log": _rel_str(result.log_path, root),
                    "workflow_status": result.status,
                }
                step["status"] = "failed" if result.status == "failed" else "completed"
                step["message"] = f"workflow `{workflow}` finished with status `{result.status}`."
                step["artifacts"] = dict(artifacts)
                if result.status == "failed":
                    workflow_error = f"workflow `{workflow}` failed"
        elif tool == "create_asset_candidate":
            asset_type = str(normalized.get("asset_type") or normalized.get("type") or "").strip()
            if not asset_type:
                step["status"] = "skipped"
                step["message"] = "asset_type is required for create_asset_candidate."
            else:
                result = create_asset_candidate(
                    root,
                    asset_type=asset_type,
                    brief=str(normalized.get("brief") or normalized.get("reason") or direction),
                    target_id=str(normalized.get("target_id") or ""),
                    provider=provider,
                )
                artifacts = {
                    "candidate": _rel_str(result.candidate_path, root),
                    "candidate_report": _rel_str(result.report_path, root),
                    "candidate_validation": _rel_str(result.validation_path, root),
                }
                step["status"] = "completed" if result.status == "pass" else "failed"
                step["message"] = f"{result.asset_type} candidate `{result.candidate_id}` created with validation `{result.status}`."
                step["artifacts"] = dict(artifacts)
        elif tool == "review_candidates":
            limit = _positive_int(normalized.get("limit"), 3)
            asset_type = str(normalized.get("asset_type") or normalized.get("type") or "")
            candidates = list_asset_candidates(root, asset_type=asset_type)[:limit]
            if not candidates:
                step["status"] = "skipped"
                step["message"] = "no candidate assets found to review."
            else:
                reviewed: list[str] = []
                for candidate in candidates:
                    path = str(candidate.get("path") or "")
                    if not path:
                        continue
                    review = review_candidate_asset(root, path, provider=provider)
                    reviewed.append(_rel_str(review.json_path, root))
                artifacts = {"review_count": str(len(reviewed))}
                if reviewed:
                    artifacts["latest_candidate_review"] = reviewed[-1]
                step["status"] = "completed" if reviewed else "skipped"
                step["message"] = f"reviewed {len(reviewed)} candidate asset(s)."
                step["artifacts"] = dict(artifacts)
    except Exception as exc:
        step["status"] = "failed"
        step["error"] = str(exc)
        step["message"] = str(exc)
        workflow_error = str(exc)

    step["ended_at"] = _now()
    return step, workflow_result, workflow_error, artifacts


def _run_director_observe_decision(
    root: Path,
    *,
    run_dir: Path,
    direction: str,
    initial_decision: dict[str, Any],
    previous_steps: list[dict[str, Any]],
    latest_step: dict[str, Any],
    deterministic: dict[str, Any],
    provider: str,
    requested_provider: str,
    step_number: int,
) -> dict[str, Any]:
    fallback = _deterministic_observe_decision(initial_decision, latest_step, deterministic)
    output_dir = run_dir / f"agent_observe_{step_number:02d}"
    agent_run = run_agent_task(
        root,
        agent_id="creative-director",
        task="observe-tool-result-and-decide",
        system_prompt=_template("director_system.md"),
        user_prompt=_director_loop_user_prompt(direction, initial_decision, previous_steps, build_director_status(root, limit=5)),
        provider=provider,
        output_dir=output_dir,
        metadata={
            "schema_name": DIRECTOR_SCHEMA,
            "loop_step": step_number,
            "requested_provider": requested_provider,
        },
        dry_run_output=fallback,
    )
    parsed_path = agent_run.run_dir / "parsed_output.json"
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    parsed = _normalize_director_decision(parsed, fallback)
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_agent_run(root, run_dir=agent_run.run_dir, schema_name=DIRECTOR_SCHEMA)
    decision = _usable_decision(parsed, fallback, validation.status)
    return {
        "decision": decision,
        "agent_run": _rel_str(agent_run.run_dir, root),
        "validation": _rel_str(validation.validation_path, root),
    }


def _deterministic_observe_decision(initial_decision: dict[str, Any], latest_step: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    decision = dict(initial_decision or fallback)
    decision["schema"] = DIRECTOR_SCHEMA_VALUE
    decision["run_id"] = str(initial_decision.get("run_id") or fallback.get("run_id") or "")
    decision["status"] = "planned"
    decision["rationale"] = "已观察上一项工具执行结果，并决定是否继续调用下一项安全工具。"
    tool = str(latest_step.get("tool") or "")
    status = str(latest_step.get("status") or "")
    if status == "failed":
        decision["director_tools"] = []
        decision["status"] = "failed"
        decision["risks"] = list(decision.get("risks", [])) + ["工具执行失败，需先处理阻塞点。"]
        return decision
    if status == "needs_user_direction":
        decision["director_tools"] = []
        decision["status"] = "needs_user_direction"
        return decision
    if tool == "record_project_direction":
        workflow = str(initial_decision.get("chosen_workflow") or fallback.get("chosen_workflow") or "none")
        if workflow != "none":
            decision["director_tools"] = [{"tool": "run_workflow", "mode": workflow, "reason": "已记录用户方向，继续推进对应创作链路。"}]
        else:
            decision["director_tools"] = [{"tool": "summarize_project_status", "reason": "已记录用户方向，刷新项目状态后收束回复。"}]
        decision["secondary_decisions"] = list(decision.get("secondary_decisions", [])) + ["已把用户自由表达转为项目方向记忆，供后续总监判断调用。"]
    elif tool == "summarize_project_status":
        decision["director_tools"] = [{"tool": "write_director_report", "reason": "项目状态已读取，收束本轮总监回复。"}]
    elif tool == "run_workflow":
        decision["director_tools"] = [{"tool": "write_director_report", "reason": "已观察工作流产物，收束本轮总监报告。"}]
        decision["secondary_decisions"] = list(decision.get("secondary_decisions", [])) + ["工作流已执行，下一步收束观察结果并形成总监回复。"]
    elif tool == "create_asset_candidate":
        decision["director_tools"] = [{"tool": "review_candidates", "limit": 3, "reason": "新候选需要先审查，再进入用户可判断的创作取舍。"}]
    elif tool == "review_candidates":
        decision["director_tools"] = [{"tool": "write_director_report", "reason": "候选审查已完成，收束本轮总监报告。"}]
    else:
        decision["director_tools"] = []
    return decision


def _director_loop_user_prompt(
    direction: str,
    initial_decision: dict[str, Any],
    previous_steps: list[dict[str, Any]],
    project_status: dict[str, Any],
) -> str:
    payload = {
        "user_direction": direction,
        "initial_decision": _decision_loop_summary(initial_decision),
        "tool_steps": previous_steps[-DIRECTOR_MAX_TOOL_STEPS:],
        "project_status": project_status,
    }
    return f"""Continue the Creative Director agent loop.

You have already made an initial decision and executed/observed one or more tools. Decide the next smallest safe tool call, or stop with an empty director_tools list.

Rules:
- Output JSON only using director_decision.v1.
- Use director_tools as the next tool calls, not as a one-shot static plan.
- Call at most one substantial creative workflow after an observation unless the observation clearly requires a different safe follow-up.
- Prefer write_director_report when enough work has been completed for this turn.
- Prefer ask_user only when the observation reveals a genuine creative contradiction or missing high-level direction.
- Do not expose file paths, workflow IDs, schema names, or agent implementation details in conversation_reply or user_visible_decisions.

Loop state:
```json
{json.dumps(payload, ensure_ascii=False, indent=2)[:16000]}
```
"""


def _next_director_tool_call(decision: dict[str, Any], previous_steps: list[dict[str, Any]]) -> dict[str, Any]:
    for tool_call in _tool_value(decision.get("director_tools")):
        normalized = _normalize_director_tool_call(tool_call)
        if not normalized.get("tool"):
            continue
        if _tool_call_already_handled(normalized, previous_steps):
            continue
        return normalized
    return {}


def _normalize_director_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    normalized = _safe_jsonable(tool_call)
    if not isinstance(normalized, dict):
        return {}
    tool = str(normalized.get("tool") or normalized.get("name") or normalized.get("action") or "").strip()
    normalized["tool"] = tool
    return normalized


def _tool_call_already_handled(tool_call: dict[str, Any], previous_steps: list[dict[str, Any]]) -> bool:
    key = _tool_call_key(tool_call)
    for step in previous_steps:
        if _tool_call_key(step.get("tool_call", {})) == key and str(step.get("status") or "") != "skipped":
            return True
    return False


def _tool_call_key(tool_call: Any) -> tuple[str, str, str]:
    if not isinstance(tool_call, dict):
        return ("", "", "")
    tool = str(tool_call.get("tool") or "").strip()
    mode = str(tool_call.get("mode") or tool_call.get("workflow") or "").strip()
    asset_type = str(tool_call.get("asset_type") or tool_call.get("type") or "").strip()
    return (tool, mode, asset_type)


def _workflow_already_executed(previous_steps: list[dict[str, Any]], workflow: str) -> bool:
    for step in previous_steps:
        if str(step.get("tool") or "") != "run_workflow":
            continue
        tool_call = step.get("tool_call", {})
        mode = str(tool_call.get("mode") or tool_call.get("workflow") or "") if isinstance(tool_call, dict) else ""
        if mode == workflow and str(step.get("status") or "") == "completed":
            return True
    return False


def _director_workflow_run_id(run_id: str, previous_steps: list[dict[str, Any]], step_number: int) -> str:
    prior = [step for step in previous_steps if str(step.get("tool") or "") == "run_workflow"]
    if not prior:
        return f"{run_id}-wf"
    return f"{run_id}-wf-{step_number:02d}"


def _is_terminal_director_tool(tool: str) -> bool:
    return tool in {"ask_user", "write_director_report"}


def _director_tool_loop_status(steps: list[dict[str, Any]], workflow_error: str) -> str:
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


def _director_loop_observation(root: Path, workflow_result: Any, workflow_error: str) -> dict[str, Any]:
    status = build_director_status(root, limit=3)
    observation = _compact_director_status(status)
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



def _decision_loop_summary(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": decision.get("intent", ""),
        "chosen_workflow": decision.get("chosen_workflow", ""),
        "status": decision.get("status", ""),
        "rationale": _trim_text(decision.get("rationale", ""), 600),
        "director_tools": _tool_value(decision.get("director_tools"))[:DIRECTOR_MAX_TOOL_STEPS],
        "user_visible_decisions": _list_value(decision.get("user_visible_decisions"))[:3],
    }


def _tool_loop_summary(steps: list[dict[str, Any]]) -> list[str]:
    summary: list[str] = []
    for step in steps:
        tool = str(step.get("tool") or "").strip()
        status = str(step.get("status") or "").strip()
        message = _trim_text(step.get("message", ""), 180)
        if tool:
            summary.append(" | ".join(part for part in [tool, status, message] if part))
    return summary
