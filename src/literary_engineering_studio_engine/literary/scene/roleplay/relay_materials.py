"""Chronological handoff from first-level scene performers to the sole prose author."""

from __future__ import annotations

import json
from typing import Any

from .relay_plan import RELAY_PLAN_SCHEMA
from .relay_scene_check import RELAY_SCENE_CHECK_SCHEMA


def render_relay_materials(
    plan: dict[str, Any], actor_entries: list[dict[str, Any]],
    environment: dict[str, Any] | None, scene_check: dict[str, Any],
) -> str:
    """Hand off only a completed, source-attributed relay as candidate material."""

    _validate_relay_materials(plan, actor_entries, scene_check)
    block = "\n".join((
        "以下是一级角色 Agent 按真实互动时间顺序生成的非权威素材，不是按人物各写一篇的整场预演。你是唯一正文作者，负责组织、取舍、叙述衔接，也可依据整个推演自行决定视角内的心理深入、情绪起伏、环境停留和句法节奏；所有说出口的话与可见人物行为仍必须回指对应角色的 entry_id，不得添加演员未生成的台词、动作、手势或操作。保留不同人的句法、避词和互动变化，不把各人的话润平成同一种解释语气，也不因素材短就把正文写成动作摘要。spoken 可作为角色主观话语，不能自动晋升为 Canon；first_person_action 须换成正文视角而不增加动作；private_impulse 是未出口的体验候选，可化为当前视角的自由间接感知、心理摇摆和情绪节奏，但不可原样转成对白、可见动作或全知断言另一角色的心事。环境候选可供取景和延展观察，不授权新线索、历史或物证。普通可弃的现场细节可以择用，承担证据或持续设定作用的细节必须有确认来源；角色主观说法不自动成为世界事实。scene_check 仅证明既定场景结果在候选中有支持，不代表所有候选细节都已证实。若编排时发现来源缺口，报告缺口，不自行补造角色言行。",
        json.dumps({"plan": plan, "actor_entries": actor_entries, "environment_candidates": environment or {},
                    "scene_check": scene_check}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 16_000:
        raise ValueError("relay material block exceeds prompt budget")
    return block


def _validate_relay_materials(
    plan: dict[str, Any], actor_entries: list[dict[str, Any]], scene_check: dict[str, Any],
) -> None:
    if not isinstance(plan, dict) or plan.get("schema") != RELAY_PLAN_SCHEMA:
        raise ValueError("relay materials require a parsed plan")
    if not isinstance(scene_check, dict) or scene_check.get("schema") != RELAY_SCENE_CHECK_SCHEMA:
        raise ValueError("relay materials require a parsed scene check")
    if scene_check.get("scene_id") != plan.get("scene_id"):
        raise ValueError("relay materials scene_id mismatch")
    statuses = scene_check.get("results")
    milestones = plan.get("milestones")
    if not isinstance(statuses, list) or not isinstance(milestones, list) or len(statuses) != len(milestones):
        raise ValueError("relay materials scene check does not cover plan")
    if any(result.get("milestone_id") != milestone.get("milestone_id") or result.get("status") != "fulfilled"
           for result, milestone in zip(statuses, milestones, strict=True)):
        raise ValueError("relay materials cannot claim incomplete scene outcomes")
    if not isinstance(actor_entries, list) or not actor_entries:
        raise ValueError("relay materials require actor entries")


__all__ = ["render_relay_materials"]
