"""Observe-and-decide stage for the creative director tool loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agent_provider import run_agent_task
from ..agent_schema import validate_agent_run
from .contracts import DIRECTOR_MAX_TOOL_STEPS, DIRECTOR_SCHEMA, DIRECTOR_SCHEMA_VALUE
from .helpers import _rel_str
from .prompts import _template
from .routing import _normalize_director_decision, _usable_decision
from .status import build_director_status
from .tool_calls import decision_loop_summary


def run_director_observe_decision(
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
    fallback = deterministic_observe_decision(initial_decision, latest_step, deterministic)
    agent_run = run_agent_task(
        root,
        agent_id="creative-director",
        task="observe-tool-result-and-decide",
        system_prompt=_template("director_system.md"),
        user_prompt=director_loop_user_prompt(
            direction,
            initial_decision,
            previous_steps,
            build_director_status(root, limit=5),
        ),
        provider=provider,
        output_dir=run_dir / f"agent_observe_{step_number:02d}",
        metadata={
            "schema_name": DIRECTOR_SCHEMA,
            "loop_step": step_number,
            "requested_provider": requested_provider,
        },
        dry_run_output=fallback,
    )
    parsed_path = agent_run.run_dir / "parsed_output.json"
    parsed = _normalize_director_decision(json.loads(parsed_path.read_text(encoding="utf-8")), fallback)
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_agent_run(root, run_dir=agent_run.run_dir, schema_name=DIRECTOR_SCHEMA)
    return {
        "decision": _usable_decision(parsed, fallback, validation.status),
        "agent_run": _rel_str(agent_run.run_dir, root),
        "validation": _rel_str(validation.validation_path, root),
    }


def deterministic_observe_decision(
    initial_decision: dict[str, Any],
    latest_step: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    decision = _observe_base(initial_decision, fallback)
    tool = str(latest_step.get("tool") or "")
    status = str(latest_step.get("status") or "")
    if status in {"failed", "needs_user_direction"}:
        return _terminal_observe_decision(decision, status)
    handlers = {
        "record_project_direction": _after_record_direction,
        "summarize_project_status": _after_summary,
        "run_workflow": _after_workflow,
        "create_asset_candidate": _after_candidate,
        "review_candidates": _after_review,
    }
    handler = handlers.get(tool)
    decision["director_tools"] = []
    if handler:
        handler(decision, initial_decision, fallback)
    return decision


def _observe_base(initial: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    decision = dict(initial or fallback)
    decision.update(
        schema=DIRECTOR_SCHEMA_VALUE,
        run_id=str(initial.get("run_id") or fallback.get("run_id") or ""),
        status="planned",
        rationale="已观察上一项工具执行结果，并决定是否继续调用下一项安全工具。",
    )
    return decision


def _terminal_observe_decision(decision: dict[str, Any], status: str) -> dict[str, Any]:
    decision["director_tools"] = []
    decision["status"] = status
    if status == "failed":
        decision["risks"] = list(decision.get("risks", [])) + ["工具执行失败，需先处理阻塞点。"]
    return decision


def _after_record_direction(decision: dict[str, Any], initial: dict[str, Any], fallback: dict[str, Any]) -> None:
    workflow = str(initial.get("chosen_workflow") or fallback.get("chosen_workflow") or "none")
    if workflow != "none":
        decision["director_tools"] = [{"tool": "run_workflow", "mode": workflow, "reason": "已记录用户方向，继续推进对应创作链路。"}]
    else:
        decision["director_tools"] = [{"tool": "summarize_project_status", "reason": "已记录用户方向，刷新项目状态后收束回复。"}]
    decision["secondary_decisions"] = list(decision.get("secondary_decisions", [])) + [
        "已把用户自由表达转为项目方向记忆，供后续总监判断调用。"
    ]


def _after_summary(decision: dict[str, Any], _initial: dict[str, Any], _fallback: dict[str, Any]) -> None:
    decision["director_tools"] = [{"tool": "write_director_report", "reason": "项目状态已读取，收束本轮总监回复。"}]


def _after_workflow(decision: dict[str, Any], _initial: dict[str, Any], _fallback: dict[str, Any]) -> None:
    decision["director_tools"] = [{"tool": "write_director_report", "reason": "已观察工作流产物，收束本轮总监报告。"}]
    decision["secondary_decisions"] = list(decision.get("secondary_decisions", [])) + [
        "工作流已执行，下一步收束观察结果并形成总监回复。"
    ]


def _after_candidate(decision: dict[str, Any], _initial: dict[str, Any], _fallback: dict[str, Any]) -> None:
    decision["director_tools"] = [
        {"tool": "review_candidates", "limit": 3, "reason": "新候选需要先审查，再进入用户可判断的创作取舍。"}
    ]


def _after_review(decision: dict[str, Any], _initial: dict[str, Any], _fallback: dict[str, Any]) -> None:
    decision["director_tools"] = [{"tool": "write_director_report", "reason": "候选审查已完成，收束本轮总监报告。"}]


def director_loop_user_prompt(
    direction: str,
    initial_decision: dict[str, Any],
    previous_steps: list[dict[str, Any]],
    project_status: dict[str, Any],
) -> str:
    payload = {
        "user_direction": direction,
        "initial_decision": decision_loop_summary(initial_decision),
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


__all__ = ["deterministic_observe_decision", "director_loop_user_prompt", "run_director_observe_decision"]
