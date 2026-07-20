"""Top-level creative director agent for user-facing orchestration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run
from .asset_workshop import create_asset_candidate, list_asset_candidates, review_candidate_asset
from .init_project import InitOptions, InitResult, init_work_project
from .model_config import MODEL_PROVIDER_CHOICES, resolve_model_provider
from .resources import engine_path
from .style_lab import active_project_style
from .workflow_runner import run_workflow


DIRECTOR_SCHEMA = "director_decision.v1"
DIRECTOR_SCHEMA_VALUE = "literary-engineering-workbench/director-decision/v0.1"
DIRECTOR_WORKFLOWS = {"project-seeding", "character-lab", "worldbuilding-lab", "outline-lab", "scene-loop"}
DIRECTOR_PROVIDERS = MODEL_PROVIDER_CHOICES
DIRECTOR_CONVERSATION_SCHEMA = "literary-engineering-workbench/director-conversation-turn/v0.1"
DIRECTOR_TOOL_LOOP_SCHEMA = "literary-engineering-workbench/director-tool-loop/v0.1"
DIRECTOR_MAX_TOOL_STEPS = 5
DIRECTOR_ALLOWED_TOOLS = {
    "init_project",
    "record_project_direction",
    "run_workflow",
    "create_asset_candidate",
    "review_candidates",
    "summarize_project_status",
    "ask_user",
    "write_director_report",
}


@dataclass(frozen=True)
class DirectorTurnResult:
    project_root: Path
    run_id: str
    status: str
    reply: str
    decision_path: Path
    report_path: Path
    agent_run_dir: Path
    validation_path: Path
    workflow_state_path: Path | None
    action: str
    artifacts: dict[str, str]
    decision: dict[str, Any]


@dataclass(frozen=True)
class DirectorBootstrapResult:
    root: Path
    title: str
    files: tuple[Path, ...]
    bootstrap_path: Path


@dataclass(frozen=True)
class DirectorToolLoopResult:
    path: Path
    status: str
    steps: list[dict[str, Any]]
    workflow_result: Any
    workflow_error: str
    artifacts: dict[str, str]


def bootstrap_project_from_direction(
    target: Path,
    direction: str,
    *,
    title: str = "",
    work_type: str = "novel",
    target_length: int = 1000000,
    language: str = "zh-CN",
) -> DirectorBootstrapResult:
    """Create a complete work-project shell from one high-level creative direction."""

    resolved_title = title.strip() or _title_from_direction(direction)
    result = init_work_project(
        InitOptions(
            target=target,
            title=resolved_title,
            work_type=work_type,
            target_length=target_length,
            language=language,
            premise=direction.strip(),
            genre=_genre_from_direction(direction),
        )
    )
    bootstrap_path = _write_bootstrap_record(result.root, direction, resolved_title, result)
    return DirectorBootstrapResult(root=result.root, title=resolved_title, files=result.files, bootstrap_path=bootstrap_path)


def run_director_turn(
    project_root: Path,
    message: str,
    *,
    provider: str = "auto",
    auto_execute: bool = True,
    agent_tasks: bool = False,
) -> DirectorTurnResult:
    """Route one user-facing creative instruction through the top-level agent."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    direction = message.strip()
    if not direction:
        raise ValueError("message is required")
    resolved_provider = resolve_model_provider(provider, purpose="creative director agent")

    run_id = _director_run_id(direction)
    run_dir = root / "director" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    project_status = build_director_status(root, limit=5)
    deterministic = _deterministic_decision(root, direction, run_id, project_status)
    agent_run = run_agent_task(
        root,
        agent_id="creative-director",
        task="route-user-direction",
        system_prompt=_template("director_system.md"),
        user_prompt=_director_user_prompt(direction, project_status),
        provider=resolved_provider,
        output_dir=run_dir / "agent_decision",
        metadata={
            "schema_name": DIRECTOR_SCHEMA,
            "auto_execute": auto_execute,
            "agent_tasks": agent_tasks,
            "requested_provider": provider,
        },
        dry_run_output=deterministic,
    )
    parsed_path = agent_run.run_dir / "parsed_output.json"
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    parsed = _normalize_director_decision(parsed, deterministic)
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_agent_run(root, run_dir=agent_run.run_dir, schema_name=DIRECTOR_SCHEMA)
    decision = _usable_decision(parsed, deterministic, validation.status)

    workflow = _safe_workflow(decision.get("chosen_workflow"), deterministic["chosen_workflow"])
    tool_loop = _run_director_tool_loop(
        root,
        run_dir=run_dir,
        direction=direction,
        initial_decision=decision,
        deterministic=deterministic,
        provider=resolved_provider,
        requested_provider=provider,
        auto_execute=auto_execute,
        agent_tasks=agent_tasks,
    )
    workflow_result = tool_loop.workflow_result
    workflow_error = tool_loop.workflow_error

    artifacts = _director_artifacts(root, agent_run.run_dir, validation.validation_path, workflow_result)
    artifacts.update(tool_loop.artifacts)
    artifacts["tool_loop"] = _rel_str(tool_loop.path, root)
    if workflow_error:
        artifacts["workflow_error"] = workflow_error
    status = _turn_status(decision, auto_execute, workflow, workflow_result, workflow_error)
    if tool_loop.status == "needs_user_direction":
        status = "needs_user_direction"
    final_decision = dict(decision)
    final_decision.update(
        {
            "status": status,
            "executed_workflow": workflow if workflow_result else "",
            "auto_execute": auto_execute,
            "agent_tasks": agent_tasks,
            "provider": resolved_provider,
            "requested_provider": provider,
            "agent_run_dir": _rel_str(agent_run.run_dir, root),
            "schema_validation": _rel_str(validation.validation_path, root),
            "workflow_state": _rel_str(workflow_result.state_path, root) if workflow_result else "",
            "workflow_status": workflow_result.status if workflow_result else "",
            "workflow_error": workflow_error,
            "tool_loop": _rel_str(tool_loop.path, root),
            "tool_loop_status": tool_loop.status,
            "tool_loop_step_count": len(tool_loop.steps),
            "tool_loop_summary": _tool_loop_summary(tool_loop.steps),
            "completed_at": _now(),
        }
    )

    decision_path = run_dir / "director_decision.json"
    report_path = run_dir / "director_report.md"
    decision_path.write_text(json.dumps(final_decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(final_decision, artifacts), encoding="utf-8")
    _append_index(root, final_decision, decision_path, report_path)
    _append_conversation_turn(root, final_decision, artifacts)
    reply = _reply(final_decision, artifacts)
    return DirectorTurnResult(
        project_root=root,
        run_id=run_id,
        status=status,
        reply=reply,
        decision_path=decision_path,
        report_path=report_path,
        agent_run_dir=agent_run.run_dir,
        validation_path=validation.validation_path,
        workflow_state_path=workflow_result.state_path if workflow_result else None,
        action="director-chat",
        artifacts=artifacts,
        decision=final_decision,
    )


def build_director_status(project_root: Path, *, limit: int = 8) -> dict[str, Any]:
    root = project_root.resolve()
    asset_items = list_asset_candidates(root) if root.is_dir() else []
    workflow_index = root / "workflow" / "runs" / "index.jsonl"
    director_index = root / "director" / "runs" / "index.jsonl"
    conversation_index = root / "director" / "conversation" / "turns.jsonl"
    direction_memory_index = root / "director" / "memory" / "project_direction.jsonl"
    return {
        "root": str(root),
        "has_project": (root / "project.yaml").exists(),
        "project_yaml": _read_text(root / "project.yaml", 3000),
        "active_style_skill": active_project_style(root) if root.is_dir() else {},
        "counts": {
            "characters": len(list((root / "characters").glob("*.yaml"))) if (root / "characters").exists() else 0,
            "scenes": len(list((root / "scenes").glob("*.yaml"))) if (root / "scenes").exists() else 0,
            "drafts": len(list((root / "drafts" / "scenes").glob("*.md"))) if (root / "drafts" / "scenes").exists() else 0,
            "candidate_assets": len(asset_items),
            "director_runs": len(_tail_jsonl(director_index, 1000)),
        },
        "candidate_assets": asset_items[-limit:],
        "recent_workflow_runs": _tail_jsonl(workflow_index, limit),
        "recent_director_runs": _tail_jsonl(director_index, limit),
        "recent_conversation": _tail_jsonl(conversation_index, limit),
        "recent_project_directions": _tail_jsonl(direction_memory_index, limit),
    }


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


def _compact_director_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_project": bool(status.get("has_project")),
        "counts": status.get("counts", {}),
        "candidate_assets": [
            {
                "asset_type": item.get("asset_type", ""),
                "candidate_id": item.get("candidate_id", ""),
                "status": item.get("status", ""),
                "title": item.get("title", ""),
            }
            for item in status.get("candidate_assets", [])[-3:]
            if isinstance(item, dict)
        ],
        "recent_conversation": [
            {
                "user_direction": item.get("user_direction", ""),
                "assistant_headline": item.get("assistant_headline", ""),
                "assistant_reply": item.get("assistant_reply", ""),
                "chosen_workflow": item.get("chosen_workflow", ""),
                "status": item.get("status", ""),
            }
            for item in status.get("recent_conversation", [])[-3:]
            if isinstance(item, dict)
        ],
        "recent_project_directions": [
            {
                "summary": item.get("summary", ""),
                "preferences": item.get("preferences", []),
                "constraints": item.get("constraints", []),
                "created_at": item.get("created_at", ""),
            }
            for item in status.get("recent_project_directions", [])[-5:]
            if isinstance(item, dict)
        ],
    }


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


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _safe_jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _safe_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_safe_jsonable(item) for item in value]
        return str(value)


def _deterministic_decision(root: Path, direction: str, run_id: str, project_status: dict[str, Any]) -> dict[str, Any]:
    intent, workflow, rationale = _route_direction(root, direction, project_status)
    if intent == "conversation":
        actions = ["record_project_direction", "summarize_project_status", "write_director_report"]
        delegated = ["creative-director"]
    elif workflow == "none":
        actions = ["summarize_project_status"]
        delegated = ["director-status"]
    else:
        actions = [f"run_{workflow}", "schema_gate_specialist_outputs", "write_director_report"]
        delegated = _delegates(workflow)
    return {
        "schema": DIRECTOR_SCHEMA_VALUE,
        "run_id": run_id,
        "user_direction": direction,
        "intent": intent,
        "chosen_workflow": workflow,
        "rationale": rationale,
        "actions": actions,
        "delegated_to": delegated,
        "director_tools": _director_tools(workflow, project_status, intent=intent, direction=direction),
        "conversation_headline": "我已记住这个创作方向" if intent == "conversation" else "",
        "conversation_reply": _conversation_memory_reply(direction) if intent == "conversation" else "",
        "secondary_decisions": _secondary_decisions("conversation" if intent == "conversation" else workflow),
        "user_visible_decisions": [
            "你只需要继续给出创作大方向、偏好的题材气质、人物重心或剧情推进目标。",
            "候选资产、审查、分支选择和工作流调度由创作总监记录并执行。",
        ],
        "constraints": [
            "新增设定先作为候选资产，不直接写入正式 canon。",
            "角色背景故事作为隐性行为因果，不在正文中直接说明，除非剧情明确揭示。",
            "所有模型输出必须保留运行记录、schema 校验记录和总监报告。",
        ],
        "risks": _risks(workflow),
        "fallback_policy": "如果模型输出未通过 director_decision.v1 校验，使用可复现的安全路由并记录原因。",
        "confidence": 0.78 if workflow != "none" else 0.9,
        "status": "planned",
    }


def _route_direction(root: Path, direction: str, project_status: dict[str, Any]) -> tuple[str, str, str]:
    text = direction.lower()
    if _has_any(text, ["状态", "摘要", "进度", "看一下", "总览", "status", "summary"]):
        return "status", "none", "用户在询问项目状态，因此只读取总监状态，不触发创作写入。"
    if _is_freeform_project_direction(text):
        return "conversation", "none", "用户正在自由表达偏好、禁忌或长期创作方向，先写入总监记忆并用于后续项目管理。"
    if _has_any(text, ["角色", "人物", "背景故事", "关系", "character", "backstory", "relationship"]):
        return "character-lab", "character-lab", "用户方向集中在人物、隐性背景或关系网，适合角色实验室。"
    if _has_any(text, ["世界观", "地点", "组织", "设定", "canon", "world", "location", "organization"]):
        return "worldbuilding-lab", "worldbuilding-lab", "用户方向集中在世界规则、地点或组织，适合世界观实验室。"
    if _has_any(text, ["大纲", "章节", "场景列表", "主线", "剧情框架", "outline", "chapter", "scene list"]):
        return "outline-lab", "outline-lab", "用户方向集中在主线结构、章节或场景列表，适合大纲实验室。"
    if _has_any(text, ["场景", "续写", "推进", "审查", "草稿", "scene", "review", "draft", "workflow"]):
        return "scene-loop", "scene-loop", "用户要求推进或审查具体创作链路，适合场景循环。"
    counts = project_status.get("counts", {}) if isinstance(project_status, dict) else {}
    if not counts.get("candidate_assets"):
        return "project-seeding", "project-seeding", "项目候选资产仍少，先从大方向孵化世界观、角色和大纲候选。"
    if not counts.get("characters"):
        return "character-lab", "character-lab", "项目缺少正式人物档案，先补充人物候选和关系压力。"
    return "scene-loop", "scene-loop", "项目已有基础资产，默认把大方向转入场景推演与审查链路。"


def _usable_decision(parsed: dict[str, Any], fallback: dict[str, Any], validation_status: str) -> dict[str, Any]:
    if validation_status == "pass":
        decision = dict(parsed)
        decision["run_id"] = str(decision.get("run_id") or fallback["run_id"])
        return decision
    decision = dict(fallback)
    decision["secondary_decisions"] = list(decision["secondary_decisions"]) + [
        "顶层模型输出未通过 director_decision.v1，已回退到确定性安全路由。"
    ]
    decision["risks"] = list(decision["risks"]) + ["本轮真实模型决策不可用，需要检查 agent_decision/schema_validation.json。"]
    return decision


def _normalize_director_decision(parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    result = _unwrap_director_payload(parsed)
    route_value = str(result.get("chosen_workflow") or result.get("workflow") or result.get("route") or result.get("intent") or "").strip()
    workflow = _safe_workflow(
        "none" if route_value == "conversation" else route_value,
        str(fallback.get("chosen_workflow") or "none"),
    )
    intent = _safe_intent(result.get("intent") or result.get("route") or workflow, str(fallback.get("intent") or "status"))
    result["schema"] = DIRECTOR_SCHEMA_VALUE
    result["run_id"] = str(result.get("run_id") or fallback.get("run_id") or "")
    result["user_direction"] = str(result.get("user_direction") or fallback.get("user_direction") or "")
    result["intent"] = intent
    result["chosen_workflow"] = workflow
    result["rationale"] = str(result.get("rationale") or result.get("reasoning") or fallback.get("rationale") or "")
    result["actions"] = _list_value(result.get("actions")) or _default_actions(workflow)
    result["delegated_to"] = _delegated_value(result) or list(fallback.get("delegated_to", []))
    result["director_tools"] = _tool_value(result.get("director_tools") or result.get("tools")) or list(fallback.get("director_tools", []))
    result["conversation_headline"] = str(result.get("conversation_headline") or result.get("headline") or "")
    result["conversation_reply"] = str(result.get("conversation_reply") or result.get("reply") or result.get("assistant_reply") or "")
    result["secondary_decisions"] = _list_value(result.get("secondary_decisions")) or list(fallback.get("secondary_decisions", []))
    result["user_visible_decisions"] = (
        _list_value(result.get("user_visible_decisions"))
        or _list_value(result.get("user_visible_choices"))
        or _list_value(result.get("user_choices"))
        or list(fallback.get("user_visible_decisions", []))
    )
    result["constraints"] = _list_value(result.get("constraints")) or list(fallback.get("constraints", []))
    result["risks"] = _list_value(result.get("risks")) or list(fallback.get("risks", []))
    result["fallback_policy"] = str(result.get("fallback_policy") or fallback.get("fallback_policy") or "")
    result["confidence"] = _confidence_value(result.get("confidence"), fallback.get("confidence", 0.5))
    result["status"] = _safe_status(result.get("status"), str(fallback.get("status") or "planned"))
    return result


def _unwrap_director_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    for key in ["director_decision", "decision", "route_decision"]:
        nested = parsed.get(key)
        if isinstance(nested, dict):
            result = dict(parsed)
            result.update(nested)
            return result
    return dict(parsed)


def _default_actions(workflow: str) -> list[str]:
    if workflow == "none":
        return ["summarize_project_status"]
    return [f"run_{workflow}", "schema_gate_specialist_outputs", "write_director_report"]


def _safe_intent(value: Any, fallback: str) -> str:
    intent = str(value or "").strip()
    if intent == "none":
        return "status"
    allowed = {"status", "conversation", *DIRECTOR_WORKFLOWS}
    if intent in allowed:
        return intent
    return fallback if fallback in allowed else "status"


def _safe_status(value: Any, fallback: str) -> str:
    status = str(value or "").strip()
    allowed = {"planned", "executed", "needs_user_direction", "failed"}
    if status in allowed:
        return status
    return fallback if fallback in allowed else "planned"


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_stringify_list_item(item) for item in value if _stringify_list_item(item)]
    if isinstance(value, dict):
        return [f"{key}: {_stringify_list_item(item)}" for key, item in value.items() if _stringify_list_item(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _delegated_value(payload: dict[str, Any]) -> list[str]:
    for key in ["delegated_to", "delegated_specialist_agents", "delegated_agents", "specialist_agents"]:
        value = payload.get(key)
        if isinstance(value, list):
            items: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    agent = str(item.get("agent") or item.get("agent_id") or item.get("name") or "").strip()
                    task = str(item.get("task") or item.get("role") or "").strip()
                    if agent and task:
                        items.append(f"{agent}: {task}")
                    elif agent:
                        items.append(agent)
                    elif task:
                        items.append(task)
                else:
                    text = _stringify_list_item(item)
                    if text:
                        items.append(text)
            return items
        normalized = _list_value(value)
        if normalized:
            return normalized
    return []


def _tool_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        tools: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                tool = str(item.get("tool") or item.get("name") or item.get("action") or "").strip()
                if not tool:
                    continue
                normalized = dict(item)
                normalized["tool"] = tool
                tools.append(normalized)
            else:
                text = _stringify_list_item(item)
                if text:
                    tools.append({"tool": text})
        return tools
    if isinstance(value, dict):
        tool = str(value.get("tool") or value.get("name") or value.get("action") or "").strip()
        return [dict(value, tool=tool)] if tool else []
    return []


def _stringify_list_item(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [f"{key}={item}" for key, item in value.items()]
        return "; ".join(parts).strip()
    if value is None:
        return ""
    return str(value).strip()


def _confidence_value(value: Any, fallback: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(fallback)
        except (TypeError, ValueError):
            return 0.5


def _safe_workflow(value: Any, fallback: str) -> str:
    workflow = str(value or "").strip()
    if workflow == "none" or workflow in DIRECTOR_WORKFLOWS:
        return workflow
    return fallback if fallback == "none" or fallback in DIRECTOR_WORKFLOWS else "none"


def _turn_status(decision: dict[str, Any], auto_execute: bool, workflow: str, workflow_result: Any, workflow_error: str) -> str:
    if workflow_error:
        return "failed"
    if not auto_execute or workflow == "none":
        return "planned" if workflow != "none" else "executed"
    if workflow_result is None:
        return str(decision.get("status") or "planned")
    return "executed" if workflow_result.status not in {"failed"} else "failed"


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


def _director_user_prompt(direction: str, project_status: dict[str, Any]) -> str:
    template = _template("director_user.md")
    return template.replace("{{USER_DIRECTION}}", direction).replace(
        "{{PROJECT_STATUS}}", json.dumps(project_status, ensure_ascii=False, indent=2)[:12000]
    )


def _template(name: str) -> str:
    path = engine_path("templates", "prompts", name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "You are a top-level literary engineering director. Output JSON only."


def _delegates(workflow: str) -> list[str]:
    mapping = {
        "project-seeding": ["worldbuilding-creator", "character-creator", "outline-creator", "asset-reviewer"],
        "character-lab": ["character-creator", "background-story-creator", "relationship-creator", "asset-reviewer"],
        "worldbuilding-lab": ["worldbuilding-creator", "location-creator", "organization-creator", "asset-reviewer"],
        "outline-lab": ["outline-creator", "chapter-plan-creator", "scene-list-creator", "asset-reviewer"],
        "scene-loop": ["memory-retriever", "roleplay-simulator", "branch-simulator", "scene-composer", "scene-reviewer", "canon-reviewer"],
    }
    return mapping.get(workflow, ["director-status"])


def _director_tools(workflow: str, project_status: dict[str, Any], *, intent: str = "", direction: str = "") -> list[dict[str, str]]:
    if intent == "conversation":
        return [
            {
                "tool": "record_project_direction",
                "summary": _conversation_memory_summary(direction),
                "preferences": [direction.strip()] if direction.strip() else [],
                "reason": "用户正在自由表达长期创作方向，需要进入总监记忆而不是暴露项目细节。",
            },
            {"tool": "summarize_project_status", "reason": "记录偏好后刷新项目状态，供下一轮自由对话继续使用。"},
            {"tool": "write_director_report", "reason": "收束本轮对话与项目记忆变更。"},
        ]
    if workflow == "none":
        return [{"tool": "summarize_project_status", "reason": "用户需要状态或方向确认。"}]
    tools: list[dict[str, str]] = []
    if not bool(project_status.get("has_project")):
        tools.append({"tool": "init_project", "reason": "先建立可维护的文学工程目录。"})
    tools.append({"tool": "run_workflow", "mode": workflow, "reason": "把用户的大方向交给对应创作链路推进。"})
    tools.append({"tool": "write_director_report", "reason": "记录本轮判断、工具计划、产物和风险。"})
    return tools


def _secondary_decisions(workflow: str) -> list[str]:
    mapping = {
        "project-seeding": [
            "先同时生成世界观、角色和大纲候选，避免单点设定过早固化。",
            "候选生成后立即进行 schema 与资产审查，不直接晋升。",
        ],
        "character-lab": [
            "优先补齐显性角色档案、隐性背景故事和关系压力。",
            "背景故事只作为行为因果，不作为默认正文说明。",
        ],
        "worldbuilding-lab": [
            "优先明确规则边界、地点压力和组织资源限制。",
            "新增能力、制度或资源只能以候选形式进入审查。",
        ],
        "outline-lab": [
            "优先建立主线、章节节奏和场景列表之间的可追踪关系。",
            "大纲候选不覆盖正式 plot，等待审查与批准。",
        ],
        "scene-loop": [
            "先构建上下文，再进行角色推演、分支推演、场景编排与 Agent 审查。",
            "场景候选可以生成，但正式发布仍走审查与审批链路。",
        ],
        "conversation": [
            "把用户自由表达的偏好、禁忌和长期方向写入总监记忆。",
            "本轮不强行触发创作工作流，下一轮可基于这些方向继续推进。",
        ],
        "none": ["只读取状态，不进行创作写入。"],
    }
    return mapping.get(workflow, mapping["none"])


def _risks(workflow: str) -> list[str]:
    if workflow == "scene-loop":
        return ["如果当前场景草稿未准备好，工作流可能只产出上下文、推演和审查提示。"]
    if workflow in DIRECTOR_WORKFLOWS:
        return ["候选资产数量可能增加，需要后续统一筛选和人工批准后再晋升。"]
    return ["本轮无写入风险。"]


def _has_any(text: str, tokens: list[str]) -> bool:
    return any(token.lower() in text for token in tokens)


def _is_freeform_project_direction(text: str) -> bool:
    preference_tokens = [
        "记住",
        "以后",
        "整体",
        "基调",
        "气质",
        "风格",
        "文风",
        "偏向",
        "更偏",
        "不要",
        "不能",
        "避免",
        "必须",
        "希望",
        "我想",
        "我喜欢",
        "我不想",
        "先聊",
        "聊聊",
        "想法",
        "方向",
        "口味",
        "偏好",
        "tone",
        "style",
        "preference",
    ]
    action_tokens = [
        "生成角色",
        "创建角色",
        "写角色",
        "生成世界观",
        "创建世界观",
        "生成大纲",
        "写大纲",
        "推进场景",
        "续写",
        "审查",
        "从零",
        "孵化",
        "完整文学项目",
        "生成一个完整",
        "创建一个",
        "写一个",
        "长篇",
    ]
    return _has_any(text, preference_tokens) and not _has_any(text, action_tokens)


def _conversation_memory_summary(direction: str) -> str:
    text = re.sub(r"\s+", " ", direction.strip())
    if not text:
        return "记录用户本轮创作偏好，供后续总监对话与项目调度使用。"
    return f"用户表达了项目长期方向或创作偏好：{_trim_text(text, 240)}"


def _conversation_memory_reply(direction: str) -> str:
    text = _trim_text(direction, 120)
    if text:
        return f"可以，我会把「{text}」作为后续判断的项目方向记忆。它不会直接改写正式设定，但会影响我接下来怎样筛选人物压力、叙事气质、冲突节奏和文风约束。你可以继续像聊天一样给我偏好；需要推进时直接说“继续”就行。"
    return "可以，我会把这轮偏好写入项目方向记忆。它不会直接改写正式设定，但会影响我后续怎样筛选人物、剧情节奏和文风约束。"


def _director_run_id(seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", seed.strip()).strip("-").lower()[:24] or "direction"
    return f"director-{stamp}-{slug}-{uuid4().hex[:6]}"


def director_project_slug(direction: str) -> str:
    text = re.sub(r"\s+", "-", direction.strip().lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", text).strip("-")
    if not text:
        return "literary-project"
    return text[:32].strip("-") or "literary-project"


def _title_from_direction(direction: str) -> str:
    text = direction.strip()
    text = re.sub(r"^(请|帮我|我要|我想|新建|创建|生成|写一个|做一个|启动)\s*", "", text)
    text = re.split(r"[。！？!?；;\n]", text)[0].strip(" ：:，,")
    if not text:
        return "未命名文学项目"
    return text[:28]


def _genre_from_direction(direction: str) -> str:
    mapping = [
        ("悬疑", "悬疑"),
        ("推理", "推理"),
        ("科幻", "科幻"),
        ("奇幻", "奇幻"),
        ("玄幻", "玄幻"),
        ("历史", "历史"),
        ("都市", "都市"),
        ("现实", "现实主义"),
        ("短剧", "短剧"),
        ("剧本", "剧本"),
        ("伪纪录", "伪纪录"),
    ]
    return " / ".join(label for token, label in mapping if token in direction) or "长篇虚构"


def _write_bootstrap_record(root: Path, direction: str, title: str, result: InitResult) -> Path:
    record_path = root / "director" / "bootstrap.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/director-bootstrap/v0.1",
        "created_at": _now(),
        "title": title,
        "user_direction": direction,
        "file_count": len(result.files),
        "files": [_rel_str(path, root) for path in result.files],
    }
    record_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record_path


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _read_text(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[:limit]


def _trim_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
