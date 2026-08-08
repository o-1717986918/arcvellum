"""Compile selected branch strategy into variable scene beats and fixed obligations."""

from __future__ import annotations

from typing import Any

from ....roleplay_lab import CharacterCard
from ..facts import SceneFacts


def build_beats(facts: SceneFacts, cards: list[CharacterCard], branch: dict[str, Any]) -> list[dict[str, Any]]:
    plan = branch.get("beat_plan")
    if isinstance(plan, list) and plan:
        return [_agent_beat(item) for item in plan if isinstance(item, dict)]
    return _fallback_beats(facts, cards, branch)


def composition_obligations(
    facts: SceneFacts,
    branch: dict[str, Any],
    rhythm_contract: dict[str, Any],
    word_budget_contract: dict[str, Any],
) -> dict[str, Any]:
    rhythm = _mapping(rhythm_contract.get("narrative_rhythm"))
    bridge = _mapping(rhythm_contract.get("scene_bridge"))
    return {
        "goal": facts.scene_goal,
        "turn": str(rhythm.get("scene_turn") or ""),
        "incoming_bridge": str(bridge.get("incoming_pressure") or ""),
        "outgoing_hook": _outgoing_hook(bridge, facts),
        "cost": str(branch.get("cost") or _writeback_cost(branch)),
        "reader_effect": str(rhythm.get("reader_effect") or branch.get("reader_effect") or ""),
        "word_target_hanzi": _word_target(word_budget_contract),
        "word_count_unit": str(word_budget_contract.get("count_unit") or "chinese_content_chars"),
    }


def _agent_beat(item: dict[str, Any]) -> dict[str, Any]:
    pace = str(item.get("pace") or "measured")
    detail = str(item.get("detail_level") or "standard")
    return {
        "beat_id": str(item.get("beat_id") or ""),
        "function": str(item.get("function") or ""),
        "visible_action": str(item.get("visible_action") or ""),
        "subtext": str(item.get("causal_change") or ""),
        "causal_change": str(item.get("causal_change") or ""),
        "craft_note": f"按 `{pace}` 速度和 `{detail}` 详略执行；不要用解释替代因果变化。",
        "pace": pace,
        "detail_level": detail,
        "serves": [str(value) for value in item.get("serves") or []],
        "source": "agent-branch-plan",
    }


def _fallback_beats(facts: SceneFacts, cards: list[CharacterCard], branch: dict[str, Any]) -> list[dict[str, Any]]:
    lead = _lead_name(cards)
    location = facts.location or "未指定地点"
    goal = facts.scene_goal or "完成当前场景目标"
    external = facts.external_conflict or "外部阻碍尚未明确"
    internal = facts.internal_conflict or "内部矛盾尚未明确"
    hook = facts.next_hooks[0] if facts.next_hooks else "为下一场景留下可追踪后果"
    action_chain = [str(item) for item in branch.get("action_chain", [])]
    premise = str(branch.get("premise") or "保持人物逻辑优先。")
    moral = _first_nonempty([card.moral_line for card in cards]) or "不突破既有人物边界"
    beats = [
        _beat("beat_01", "开场压力", f"以 `{location}` 中一个可观察异常切入，让 {lead} 在行动前先感到约束。", f"不要解释背景；让 `{external}` 成为动作节奏、停顿或视线选择上的压力。", _pick(action_chain, 0, f"建立目标：{goal}")),
        _beat("beat_02", "接近目标", f"{lead} 采取一个低声量、可执行的动作接近目标：{goal}。", f"内部矛盾 `{internal}` 通过犹豫、绕路、避开某个词或检查同伴安全体现。", _pick(action_chain, 1, premise)),
        _beat("beat_03", "阻碍升级", f"外部阻碍推进一格，但不要让偶然性替角色做决定：{external}。", "让场景压力来自已登记信息、地点规则和人物选择，不用突然降临的便利转折。", _pick(action_chain, 2, "把冲突写成行动上的具体障碍。")),
        _beat("beat_04", "人物选择", f"{lead} 做出一个符合当前 BDI 的选择，并保留代价。", f"选择必须受 `{moral}` 约束；背景故事只能作为隐性动因，不得直白交代。", _pick(action_chain, 3, "用选择暴露人物，而不是用旁白解释人物。")),
        _beat("beat_05", "后果落点", f"场景结尾留下状态变化或下一场景输入：{hook}。", "只确认已经写进动作的后果；新增事实保持候选状态，等待审查写回。", "结尾不要总结主题，让可追踪后果自己留下余音。"),
    ]
    metadata = [
        ("compressed", "lean", ["incoming_bridge"]),
        ("measured", "standard", ["goal"]),
        ("accelerating", "standard", ["turn"]),
        ("slow", "expanded", ["cost"]),
        ("decelerating", "standard", ["reader_effect", "outgoing_hook"]),
    ]
    for beat, (pace, detail, serves) in zip(beats, metadata):
        beat.update({"pace": pace, "detail_level": detail, "serves": serves, "source": "deterministic-fallback"})
    return beats


def _beat(beat_id: str, function: str, visible_action: str, subtext: str, craft_note: str) -> dict[str, Any]:
    return {"beat_id": beat_id, "function": function, "visible_action": visible_action, "subtext": subtext, "craft_note": craft_note}


def _outgoing_hook(bridge: dict[str, Any], facts: SceneFacts) -> str:
    direct = str(bridge.get("outgoing_hook") or "").strip()
    if direct:
        return direct
    hooks = bridge.get("outgoing_hooks")
    if isinstance(hooks, list) and hooks:
        first = hooks[0]
        return str(first.get("content") or "") if isinstance(first, dict) else str(first)
    return facts.next_hooks[0] if facts.next_hooks else ""


def _writeback_cost(branch: dict[str, Any]) -> str:
    writeback = _mapping(branch.get("writeback_candidates"))
    for field in ("character_changes", "relationship_changes", "new_facts", "next_scene_inputs"):
        values = writeback.get(field)
        if isinstance(values, list) and values:
            return str(values[0])
    return ""


def _word_target(contract: dict[str, Any]) -> int:
    return int(contract.get("target_chinese_chars") or contract.get("scene_yaml_target_chinese_chars") or 0)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick(items: list[str], index: int, default: str) -> str:
    return items[index] if index < len(items) and items[index].strip() else default


def _lead_name(cards: list[CharacterCard]) -> str:
    return cards[0].name or cards[0].character_id if cards else "核心角色"


def _first_nonempty(items: list[str]) -> str:
    return next((str(item).strip() for item in items if str(item).strip()), "")
