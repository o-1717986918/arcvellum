"""Pure literary-plan construction for a scene composition packet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.literary.scene.roleplay.lab import CharacterCard, _load_characters
from ..facts import SceneFacts


def build_subtext_map(
    facts: SceneFacts,
    cards: list[CharacterCard],
) -> list[dict[str, Any]]:
    if not cards:
        return [_unknown_subtext(facts)]
    return [_character_subtext(facts, card) for card in cards]


def build_dialogue_intents(
    facts: SceneFacts,
    cards: list[CharacterCard],
) -> list[dict[str, Any]]:
    if not cards:
        return [
            {
                "speaker": "未建档角色",
                "wants": facts.scene_goal or "推进场景。",
                "avoids": facts.internal_conflict or "未填写。",
                "speech_strategy": "先补人物 speech_style，再生成对白。",
                "forbidden_exposition": "不得用对白直接解释世界观和背景故事。",
            }
        ]
    return [_dialogue_intent(facts, card) for card in cards]


def build_perceptual_options(facts: SceneFacts) -> dict[str, object]:
    """Expose only grounded material; absence is preferable to stock sensations."""

    return {
        "location_anchor": facts.location,
        "motifs": list(facts.active_foreshadowing),
        "sound": [],
        "texture": [],
        "light": [],
    }


def build_expression_plan(
    facts: SceneFacts,
    rhythm: dict[str, Any],
) -> dict[str, object]:
    """Describe choices the writer can make without supplying reusable prose."""

    rhythm_state = rhythm.get("narrative_rhythm") if isinstance(rhythm.get("narrative_rhythm"), dict) else {}
    active = ["syntax_motion"]
    if len(facts.participants) > 1:
        active.append("dialogue_pressure")
    if facts.active_foreshadowing or any(
        marker in facts.external_conflict for marker in ("秘密", "真相", "线索", "发现", "隐瞒", "误认")
    ):
        active.append("information_strategy")
    return {
        "schema": "literary-engineering-workbench/scene-expression-plan/v1",
        "focalization_lens": facts.viewpoint or "由当前视角人物的已知信息与误判决定",
        "information_strategy": "依据已确认的读者问题与暂扣信息选择揭示顺序",
        "syntax_motion": str(rhythm_state.get("paragraph_shape") or "句法随行动和关系压力变化"),
        "dialogue_pressure": facts.internal_conflict or "依据人物的当下目标与关系位置决定",
        "evidence_channel": "选择当前因果所需的动作、对白、物证、直述、沉默或环境；允许直接命名情绪",
        "ending_residue": facts.next_hooks[0] if facts.next_hooks else "保留本场变化造成的下一步压力",
        "active_axes": active[:3],
    }


def project_brief_expression_context(project_root: Path, brief: dict[str, Any]) -> dict[str, Any]:
    """Share the composition expression/voice rules with the lean runtime."""

    rhythm = brief.get("rhythm") if isinstance(brief.get("rhythm"), dict) else {}
    participants = [str(item) for item in brief.get("participants", []) if str(item).strip()]
    facts = SceneFacts(
        scene_id=str(brief.get("scene_id") or "scene"),
        chapter_id="",
        location=str(brief.get("location") or ""),
        participants=participants,
        canon_refs=[],
        active_foreshadowing=[],
        scene_goal=str(brief.get("objective") or ""),
        external_conflict=str(brief.get("external_conflict") or ""),
        internal_conflict=str(brief.get("internal_conflict") or ""),
        style_constraints=[],
        next_hooks=[],
        viewpoint=str(brief.get("viewpoint") or ""),
    )
    cards = [
        card for card in _load_characters(project_root)
        if any(_same_character(item, card) for item in participants)
    ]
    paragraph_shape = str(rhythm.get("pace") or "")
    return {
        "expression_plan": build_expression_plan(facts, {"narrative_rhythm": {"paragraph_shape": paragraph_shape}}),
        "dialogue_intents": build_dialogue_intents(facts, cards),
        "perceptual_options": build_perceptual_options(facts),
    }


def revision_targets(
    facts: SceneFacts,
    cards: list[CharacterCard],
    branch: dict[str, Any],
) -> list[str]:
    targets = [
        "把每个节拍改写成具体动作、可观察细节和状态变化。",
        "删掉解释性背景段落，让 background_story 只通过选择、回避、误判、语气和关系压力体现。",
        "生成正文后运行 review-scene；涉及新增事实时继续运行 canon-lint。",
    ]
    if not cards and facts.participants:
        targets.append("participants 没有匹配正式人物档案，先补人物卡或修正 scene.yaml。")
    if branch.get("status") == "no_manifest":
        targets.append("建议先运行 branch-simulate，再基于评分分支重建 compose-scene。")
    if branch.get("source") != "selection":
        targets.append("当前分支未经过正式 branch_selection，不能直接进入 generate-scene。")
    if not facts.canon_refs:
        targets.append("scene.yaml 缺少 canon_refs，正稿前应补硬约束引用。")
    return targets


def guardrails() -> list[str]:
    return [
        "composition 是写作编排，不是正稿。",
        "不得新增未经确认的 canon。",
        "不得改变人物、地点、时间线或规则的适用范围。",
        "不得把角色 background_story 直接写成说明段落。",
        "不得让分支推荐绕过人工选择、审查和发布门禁。",
        "只有 selection_source=selection 的 composition 才能进入 generate-scene；内部实验必须显式放行。",
    ]


def flow_gate(branch: dict[str, Any]) -> dict[str, Any]:
    source = str(branch.get("source") or "")
    return {
        "branch_selection_required": True,
        "ready_for_generation": source == "selection",
        "selection_source": source,
        "selection_gate": branch.get("selection_gate", {}),
        "blocking_reason": ""
        if source == "selection"
        else "branch_selection.md has not recorded a formal selected branch",
    }


def character_payload(card: CharacterCard, root: Path) -> dict[str, Any]:
    return {
        "file": _relative(card.file, root),
        "character_id": card.character_id,
        "name": card.name,
        "role": card.role,
        "belief": card.belief,
        "desire": card.desire,
        "intention": card.intention,
        "fear": card.fear,
        "secret": card.secret,
        "background_story": {
            "summary": card.background_summary,
            "formative_events": card.formative_events,
            "behavior_influences": card.behavior_influences,
            "reveal_policy": card.reveal_policy,
        },
        "moral_line": card.moral_line,
        "speech_style": card.speech_style,
        "speech_style_details": card.speech_style_details,
        "relationships": card.relationships,
        "known_facts": card.known_facts,
    }


def serializable_branch(branch: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        key: _relative(value, root) if isinstance(value, Path) else value
        for key, value in branch.items()
    }


def _unknown_subtext(facts: SceneFacts) -> dict[str, Any]:
    return {
        "character_id": "unknown",
        "name": "未建档角色",
        "public_action": facts.scene_goal or "按场景目标行动。",
        "hidden_pressure": facts.internal_conflict or "人物隐性压力未填写。",
        "background_influence": "缺少正式人物 background_story，建议先补人物档案。",
        "do_not_write_directly": ["不要用万能旁白替代人物动机。"],
    }


def _character_subtext(facts: SceneFacts, card: CharacterCard) -> dict[str, Any]:
    return {
        "character_id": card.character_id,
        "name": card.name,
        "public_action": _first_nonempty(card.intention)
        or facts.scene_goal
        or "完成当前场景任务。",
        "hidden_pressure": _first_nonempty(card.fear + card.secret)
        or facts.internal_conflict
        or "隐性压力未填写。",
        "background_influence": _first_nonempty(card.behavior_influences)
        or "以选择、回避、误判、语气或沉默体现过往影响。",
        "reveal_policy": card.reveal_policy or "implicit_only",
        "do_not_write_directly": [
            "不得直白交代人物背景故事。",
            "不得把人物心理写成设定说明书。",
            "不得为了推进剧情让角色无解释违背 BDI。",
        ],
    }


def _dialogue_intent(facts: SceneFacts, card: CharacterCard) -> dict[str, Any]:
    stable_voice = card.speech_style_details or {"rhythm": card.speech_style}
    interlocutors = [name for name in facts.participants if not _same_character(name, card)]
    return {
        "speaker": card.name or card.character_id,
        "wants": _first_nonempty(card.desire + card.intention)
        or facts.scene_goal
        or "推进当前场景目标。",
        "avoids": _first_nonempty(card.fear + card.secret)
        or facts.internal_conflict
        or "避免暴露过多信息。",
        "speech_strategy": card.speech_style or "让语气服务关系压力，少解释，多留白。",
        "stable_voice": stable_voice,
        "voice_state": {
            "interlocutors": interlocutors,
            "relationship_evidence": card.relationships,
            "known_facts": card.known_facts,
            "current_goal": _first_nonempty(card.desire + card.intention) or facts.scene_goal,
            "withheld_or_misread": _first_nonempty(card.secret + card.fear) or facts.internal_conflict,
            "speech_action": ("试探或回避" if card.secret else "争取、拒绝或追问")
            + (f"；对象：{'、'.join(interlocutors)}" if interlocutors else "；以当前场景压力决定"),
        },
        "forbidden_exposition": "不得借对白直接讲述 background_story；只能让语气、停顿和避词泄露压力。",
    }


def _first_nonempty(items: list[str]) -> str:
    return next((item for item in items if item), "")


def _same_character(reference: str, card: CharacterCard) -> bool:
    return reference in {card.name, card.character_id, card.file.stem} or reference.rsplit("/", 1)[-1] in {
        card.character_id, card.file.stem,
    }


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "build_dialogue_intents",
    "build_expression_plan",
    "build_perceptual_options",
    "project_brief_expression_context",
    "build_subtext_map",
    "character_payload",
    "flow_gate",
    "guardrails",
    "revision_targets",
    "serializable_branch",
]
