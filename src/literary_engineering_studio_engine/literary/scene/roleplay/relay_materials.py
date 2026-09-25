"""Chronological handoff from first-level scene performers to the sole prose author."""

from __future__ import annotations

import json
from typing import Any

from .relay_plan import RELAY_PLAN_SCHEMA
from .relay_scene_check import RELAY_SCENE_CHECK_SCHEMA


def render_relay_materials(
    plan: dict[str, Any], actor_entries: list[dict[str, Any]],
    environment: dict[str, Any] | None, scene_check: dict[str, Any], *, viewpoint: str = "",
) -> str:
    """Hand off only a completed, source-attributed relay as candidate material."""

    _validate_relay_materials(plan, actor_entries, scene_check)
    block = "\n".join((
        "以下是一级角色 Agent 按真实互动时间顺序生成的候选素材。你是唯一正文作者，负责组织、取舍、叙述衔接，也可依据整个推演自行决定视角内的心理深入、情绪起伏、环境停留和句法节奏；人物发言的意图与回合、可见行为须回指对应角色的 entry_id。你可改写已有台词的具体措辞和语势。保留不同人的句法、避词和互动变化。spoken 是角色主观话语；first_person_action 换成正文视角；private_impulse 是未出口的体验候选，可化为当前视角的自由间接感知、心理摇摆和情绪节奏。环境候选可供取景和延展观察。普通现场细节可以择用，承担证据或持续设定作用的细节须有确认来源。scene_check 证明既定场景结果在候选中有支持。若编排时发现来源缺口，报告缺口。",
        json.dumps({"plan": plan, "actor_entries": _viewpoint_entries(actor_entries, viewpoint), "environment_candidates": environment or {},
                    "scene_check": scene_check}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 16_000:
        raise ValueError("relay material block exceeds prompt budget")
    return block


def _viewpoint_entries(entries: list[dict[str, Any]], viewpoint: str) -> list[dict[str, Any]]:
    if not viewpoint:
        return entries
    return [{**entry, "private_impulse": ""} if entry.get("speaker") != viewpoint else entry
            for entry in entries]


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
