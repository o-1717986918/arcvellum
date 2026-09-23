"""Source-grounded dramatic milestones for optional character relay."""

from __future__ import annotations

import json
from typing import Any

from .performance import _parse_unknown_slots
from .relay_context import validated_knowledge_quotes, validated_opening_situation, validated_pending_outcome


RELAY_PLAN_SCHEMA = "arcvellum/scene-relay-plan/v2"
MAX_RELAY_MILESTONES = 4


def render_relay_plan_prompt(brief: dict[str, Any]) -> str:
    """Ask the main creator for locked plot endpoints, never actor line readings."""

    evidence = {key: brief.get(key) for key in (
        "scene_id", "participants", "location", "objective", "scene_function",
        "canon_constraints", "incoming_handoff", "chapter_obligations", "rhythm",
    )}
    return f"""# Scene Relay Dramatic Floor

你是唯一主创的场景编排阶段。只从 SceneBrief 中挑出一至 {MAX_RELAY_MILESTONES} 个本场必须成立的剧情结果，按大致因果顺序列出，并标出该变化归属的现有参与者。它们是场景边界，不是角色的轮流发言表，更不是每轮必须完成的任务。source_quote 必须逐字出现在 SceneBrief 的 objective、scene_function、rhythm.scene_turn、canon_constraints 或 chapter_obligations 中；可以截取其中最短的完整事实分句，不必引用整段，不可改写、扩写或发明。一个 milestone 只对应一次因果变化：如果原文用分号串联了“漏歌后纠正”和“承认删点名”，它们须分成两个 milestone，但不因此指定两次演员调用或两句台词。每个结果只规定事实终点，绝不指定台词、句式、情绪、手势、回应顺序或环境描写。角色将根据真实对手言行自主表演，可拖延、回避、抵抗或改变抵达结果的条件；主创须等自然互动展开后再检查场景结果，不能逐轮催交。

opening_situation 从 scene_function 或 location 逐字摘出当前会面的地点、身份与话题等开场处境；它是身处的局面，不是先说哪句话的命令，也不能包含尚未发生的结果。scene_function 若本来只用一句话描述会面，可引用整句。actor_knowledge 只从 incoming_handoff 中逐字选取每个角色在开场前确实知道、且与当前会面直接相关的最短事实分句，最多每人三条；上一场出现的道具、登记簿或动作是过去，不等于此刻带在身边。无关的旧交接留空，不知道的内容也留空。不要把未来结果伪装为角色已经知道或已经见到的事实。unknown_slots 只列本场容易误写成确定事实的少量关键空位，不预告其他场景的秘密，也不规定人物表现。环境写手另行独立创作，你不分配光、声、物件和段落。

## SceneBrief 相关事实
{json.dumps(evidence, ensure_ascii=False)}

仅返回 JSON：{{"scene_id":"与 SceneBrief 相同","opening_situation":"scene_function 或 location 中逐字摘录的当前会面处境","milestones":[{{"speaker":"participants 中精确名字","source_quote":"SceneBrief 中逐字摘录的既定结果"}}],"actor_knowledge":[{{"speaker":"participants 中精确名字","quotes":["incoming_handoff 中逐字摘录的已发生事实"]}}],"unknown_slots":["尚未确认的关键事实空位"]}}。actor_knowledge 必须覆盖全部 participants；没有额外知情就给空数组。不要输出正文或标准台词。"""


def parse_relay_plan(payload: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("scene_id") != brief.get("scene_id"):
        raise ValueError("relay plan scene_id mismatch")
    participants = set(brief.get("participants") or ())
    opening_situation = validated_opening_situation(brief, payload.get("opening_situation"))
    milestones = _parse_milestones(payload.get("milestones"), participants, brief)
    knowledge = _parse_actor_knowledge(payload.get("actor_knowledge"), participants, brief)
    unknown_slots = _parse_unknown_slots(payload.get("unknown_slots"))
    return {
        "schema": RELAY_PLAN_SCHEMA, "scene_id": brief["scene_id"], "opening_situation": opening_situation,
        "milestones": milestones, "actor_knowledge": knowledge, "unknown_slots": unknown_slots,
    }


def _parse_milestones(value: Any, participants: set[str], brief: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_RELAY_MILESTONES:
        raise ValueError("relay plan requires one to four milestones")
    milestones = []
    for number, item in enumerate(value, 1):
        if not isinstance(item, dict) or item.get("speaker") not in participants:
            raise ValueError("relay milestone speaker mismatch")
        quote = item.get("source_quote")
        if not isinstance(quote, str):
            raise ValueError("relay milestone source_quote is missing")
        if "；" in quote or ";" in quote:
            raise ValueError("relay milestone source_quote must name one plot change")
        try:
            validated_pending_outcome(brief, quote)
        except ValueError as exc:
            raise ValueError("relay milestone source_quote is not a confirmed plot result") from exc
        milestones.append({"milestone_id": f"m{number}", "speaker": item["speaker"], "source_quote": quote.strip()})
    if len({item["source_quote"] for item in milestones}) != len(milestones):
        raise ValueError("relay milestones must be distinct")
    return milestones


def _parse_actor_knowledge(value: Any, participants: set[str], brief: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(participants):
        raise ValueError("relay actor_knowledge must cover every participant")
    handoff = [item for item in (brief.get("incoming_handoff") or ()) if isinstance(item, str)]
    knowledge = [_parse_person_knowledge(item, participants, brief, handoff) for item in value]
    if {item["speaker"] for item in knowledge} != participants:
        raise ValueError("relay actor_knowledge must have unique participants")
    return knowledge


def _parse_person_knowledge(
    item: Any, participants: set[str], brief: dict[str, Any], handoff: list[str],
) -> dict[str, Any]:
    if not isinstance(item, dict) or item.get("speaker") not in participants:
        raise ValueError("relay actor_knowledge speaker mismatch")
    quotes = item.get("quotes")
    if not isinstance(quotes, list) or len(quotes) > 3:
        raise ValueError("relay actor_knowledge quotes exceed three")
    normalized = validated_knowledge_quotes(brief, quotes)
    if any(not any(quote in source for source in handoff) for quote in normalized):
        raise ValueError("relay actor_knowledge must quote incoming_handoff")
    return {"speaker": item["speaker"], "quotes": normalized}


__all__ = ["RELAY_PLAN_SCHEMA", "render_relay_plan_prompt", "parse_relay_plan"]
