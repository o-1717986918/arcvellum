"""Deterministic fallback branch strategies and evidence-aware scoring."""

from __future__ import annotations

from ....roleplay_lab import CharacterCard
from ..facts import SceneFacts
from .contracts import BranchCandidate, SCORE_KEYS


_ARCHETYPES = (
    ("branch_character_inevitable", "人物逻辑优先", "让角色按照当前 BDI 做最真实、最少作者操控感的选择。"),
    ("branch_conflict_escalation", "冲突升级优先", "把外部阻碍和内部矛盾同时推高，让场景产生强转折。"),
    ("branch_foreshadowing_return", "伏笔收益优先", "优先回收或加固既有伏笔，让当前场景服务长线结构。"),
    ("branch_moral_cost", "道德代价优先", "让角色为了目标付出可见代价，但不突破人物道德底线。"),
    ("branch_quiet_consequence", "余波沉淀优先", "降低表层动作，放大选择后的关系余波和主题回声。"),
)


def build_fallback_candidates(
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
    branch_count: int,
    roleplay_result: dict[str, object] | None = None,
) -> list[BranchCandidate]:
    evidence = roleplay_result or {}
    return [
        _candidate(branch_id, title, strategy, scene, active_cards, all_cards, evidence)
        for branch_id, title, strategy in _ARCHETYPES[:branch_count]
    ]


def _candidate(
    branch_id: str,
    title: str,
    strategy: str,
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
    roleplay: dict[str, object],
) -> BranchCandidate:
    names = [card.name or card.character_id for card in (active_cards or all_cards)]
    lead = names[0] if names else "核心角色"
    premise, actions, base = _strategy_content(branch_id, scene, lead)
    _add_roleplay_evidence(actions, roleplay)
    risks = [
        *_roleplay_strings(roleplay.get("canon_risks"), limit=2),
        *_risks(branch_id, scene, active_cards, all_cards),
    ]
    scores = _scores(base, scene, active_cards, all_cards)
    total = sum(scores.values())
    status = (
        "candidate"
        if total >= 17 and not _blocking_context_risk(risks)
        else "needs_detail"
    )
    return BranchCandidate(
        branch_id=branch_id,
        title=title,
        strategy=strategy,
        premise=premise,
        action_chain=actions,
        character_tests=_character_tests(active_cards, all_cards),
        canon_checks=_canon_checks(scene),
        risks=risks,
        writeback_candidates=_writeback(branch_id, scene, lead, roleplay),
        scores=scores,
        total_score=total,
        status=status,
    )


def _strategy_content(
    branch_id: str,
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    builders = {
        "branch_character_inevitable": _character_inevitable,
        "branch_conflict_escalation": _conflict_escalation,
        "branch_foreshadowing_return": _foreshadowing_return,
        "branch_moral_cost": _moral_cost,
        "branch_quiet_consequence": _quiet_consequence,
    }
    return builders.get(branch_id, _quiet_consequence)(scene, lead)


def _character_inevitable(
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    return (
        f"{lead} 不选择最戏剧化的路，而选择最符合当前欲望和恐惧的路。",
        [
            f"{lead} 先确认自己真正要达成的目标：{_goal(scene)}",
            f"角色绕开便利情节，正面处理内部矛盾：{_internal(scene)}",
            f"外部阻碍以低烈度但高约束的方式介入：{_external(scene)}",
            f"场景结束时留下后果：{_hook(scene)}",
        ],
        _base_scores(5, 4, 3, 3, 4),
    )


def _conflict_escalation(
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    return (
        f"{_location(scene)} 的外部阻碍升级，迫使 {lead} 在不完整信息下行动。",
        [
            f"外部冲突被推到台前：{_external(scene)}",
            f"{lead} 的短期行动解决一个小问题，同时制造更大的结构性麻烦。",
            f"内部矛盾被暴露：{_internal(scene)}",
            "结尾留下一个必须在后续章节处理的公开后果。",
        ],
        _base_scores(3, 3, 5, 4, 4),
    )


def _foreshadowing_return(
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    foreshadow = (
        scene.active_foreshadowing[0]
        if scene.active_foreshadowing
        else "尚未登记的潜在伏笔"
    )
    return (
        f"当前场景围绕 `{foreshadow}` 做一次轻量回收或二次埋设。",
        [
            f"让 {lead} 注意到一个与伏笔有关的细节，而不是直接解释真相。",
            f"该细节改变角色对目标的判断：{_goal(scene)}",
            "伏笔只推进一格，不在当前场景一次性说尽。",
            f"下一场景继承线索：{_hook(scene)}",
        ],
        _base_scores(3, 4, 3, 4, 5),
    )


def _moral_cost(
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    return (
        f"{lead} 可以接近目标，但必须付出关系、名誉或自我认知上的代价。",
        [
            f"{lead} 面对目标：{_goal(scene)}",
            "角色拒绝突破道德底线，但接受一个更慢、更痛的方案。",
            f"内部矛盾被压实：{_internal(scene)}",
            "场景结束时生成需要人工确认的人物状态变化。",
        ],
        _base_scores(4, 3, 4, 5, 4),
    )


def _quiet_consequence(
    scene: SceneFacts,
    lead: str,
) -> tuple[str, list[str], dict[str, int]]:
    return (
        f"场景不追求强反转，而让 {lead} 的选择在关系和主题层面留下余波。",
        [
            f"保留场景目标：{_goal(scene)}",
            f"让地点 `{_location(scene)}` 成为情绪和关系压力的承载物。",
            "用一个克制行动替代大段解释。",
            "把后果写成可被后续审计追踪的状态变化。",
        ],
        _base_scores(4, 5, 2, 4, 3),
    )


def _base_scores(
    character_logic: int,
    canon_safety: int,
    dramatic_tension: int,
    literary_potential: int,
    longterm_payoff: int,
) -> dict[str, int]:
    return dict(
        zip(
            SCORE_KEYS,
            (
                character_logic,
                canon_safety,
                dramatic_tension,
                literary_potential,
                longterm_payoff,
            ),
            strict=True,
        )
    )


def _goal(scene: SceneFacts) -> str:
    return scene.scene_goal or "完成当前场景目标"


def _external(scene: SceneFacts) -> str:
    return scene.external_conflict or "外部阻碍尚未明确"


def _internal(scene: SceneFacts) -> str:
    return scene.internal_conflict or "内部矛盾尚未明确"


def _hook(scene: SceneFacts) -> str:
    return scene.next_hooks[0] if scene.next_hooks else "为下一场景留下可追踪后果"


def _location(scene: SceneFacts) -> str:
    return scene.location or "未指定地点"


def _add_roleplay_evidence(actions: list[str], roleplay: dict[str, object]) -> None:
    action = _roleplay_strings(roleplay.get("character_actions"), limit=2)
    consequence = _roleplay_strings(roleplay.get("world_consequences"), limit=2)
    pressure = _roleplay_strings(roleplay.get("branch_pressures"), limit=2)
    if action:
        actions.insert(1, "RP 角色行动依据：" + "；".join(action))
    if consequence:
        actions.append("RP 世界后果：" + "；".join(consequence))
    if pressure:
        actions.append("RP 分支压力：" + "；".join(pressure))


def _scores(
    base: dict[str, int],
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> dict[str, int]:
    scores = dict(base)
    if not scene.scene_goal:
        scores["character_logic"] -= 1
        scores["longterm_payoff"] -= 1
    if not scene.external_conflict and not scene.internal_conflict:
        scores["dramatic_tension"] -= 1
    if not active_cards and not all_cards:
        scores["character_logic"] -= 2
        scores["literary_potential"] -= 1
    if any(_has_background_story(card) for card in active_cards or all_cards):
        scores["character_logic"] += 1
        scores["literary_potential"] += 1
    if not scene.canon_refs:
        scores["canon_safety"] -= 1
    if scene.active_foreshadowing or scene.next_hooks:
        scores["longterm_payoff"] += 1
    return {key: _clamp(scores.get(key, 1)) for key in SCORE_KEYS}


def _risks(
    branch_id: str,
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> list[str]:
    risks: list[str] = []
    if not scene.scene_goal:
        risks.append("场景缺少 scene_goal，分支目标需要人工补齐。")
    if not scene.location:
        risks.append("场景缺少 location，世界后果判断不稳定。")
    if scene.participants and not active_cards:
        risks.append("场景 participants 未匹配正式人物档案，人物行动需要人工核对。")
    if not active_cards and not all_cards:
        risks.append("缺少正式人物档案，人物合理性评分只能作为占位。")
    if (active_cards or all_cards) and not any(
        _has_background_story(card) for card in active_cards or all_cards
    ):
        risks.append("人物缺少 background_story，隐性行为因果较弱。")
    if branch_id == "branch_foreshadowing_return" and not scene.active_foreshadowing:
        risks.append("没有登记 active_foreshadowing，伏笔收益分支需要人工指定线索。")
    if not scene.canon_refs:
        risks.append("场景 input_state.canon_refs 为空，正式合并前应补 canon 引用。")
    risks.append("任何新增事实都必须进入人工确认，不得直接写入 canon。")
    return risks


def _blocking_context_risk(risks: list[str]) -> bool:
    return any(
        "缺少正式人物档案" in risk
        or "缺少 scene_goal" in risk
        or "participants 未匹配" in risk
        for risk in risks
    )


def _writeback(
    branch_id: str,
    scene: SceneFacts,
    lead: str,
    roleplay: dict[str, object],
) -> dict[str, list[str]]:
    label = branch_id.removeprefix("branch_")
    roleplay_writeback = _roleplay_strings(roleplay.get("writeback_candidates"), limit=3)
    return {
        "new_facts": [f"{scene.scene_id} 产生 `{label}` 分支候选，等待人工决定是否进入主线。", *roleplay_writeback],
        "character_changes": [f"{lead} 在 `{label}` 分支中出现可审查的行动倾向变化。"],
        "relationship_changes": ["如涉及关系变化，先写入候选，不直接覆盖人物档案。"],
        "foreshadowing_changes": [f"检查 `{label}` 是否新增、加固或回收伏笔。"],
        "next_scene_inputs": [scene.next_hooks[0] if scene.next_hooks else "为下一场景补一条明确输入状态。"],
    }


def _roleplay_strings(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("summary")
                or item.get("chosen_action")
                or item.get("pressure")
                or item.get("risk")
                or item.get("content")
                or ""
            ).strip()
        else:
            text = ""
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _character_tests(
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> list[str]:
    cards = active_cards or all_cards
    if not cards:
        return ["补齐人物 BDI 后重新评估。"]
    tests: list[str] = []
    for card in cards:
        tests.append(f"{card.name} 的行动必须能由 belief / desire / intention 至少两项解释。")
        if _has_background_story(card):
            tests.append(f"{card.name} 的背景故事只能通过选择、回避、误判或语气间接影响行动，不得直接讲述。")
        if card.moral_line:
            tests.append(f"{card.name} 不得无解释突破道德边界：{card.moral_line}")
    return tests


def _canon_checks(scene: SceneFacts) -> list[str]:
    checks = ["不得自动确认新增事实。", "不得改变已确认适用范围、时间线和人物关系。"]
    if scene.canon_refs:
        checks.append("逐条核对 canon refs：" + "、".join(scene.canon_refs))
    else:
        checks.append("补充 input_state.canon_refs 后再进入正稿。")
    return checks


def _has_background_story(card: CharacterCard) -> bool:
    return bool(
        card.background_summary or card.formative_events or card.behavior_influences
    )


def _clamp(value: int) -> int:
    return max(1, min(5, value))


__all__ = ["build_fallback_candidates"]
