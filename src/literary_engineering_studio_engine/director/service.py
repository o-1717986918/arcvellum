"""Public creative-director application service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agent_provider import run_agent_task
from ..agent_schema import validate_agent_run
from ..model_config import resolve_model_provider
from .bootstrap import _director_run_id
from .contracts import DIRECTOR_SCHEMA, DirectorTurnResult
from .helpers import _now, _rel_str
from .loop import _run_director_tool_loop, _tool_loop_summary
from .prompts import _director_user_prompt, _template
from .records import _append_conversation_turn, _append_index, _director_artifacts, _render_report, _reply
from .routing import _deterministic_decision, _normalize_director_decision, _safe_workflow, _turn_status, _usable_decision
from .status import build_director_status

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
