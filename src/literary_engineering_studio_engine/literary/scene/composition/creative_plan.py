"""Pure literary-plan construction for a scene composition packet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....roleplay_lab import CharacterCard
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
) -> list[dict[str, str]]:
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


def build_sensory_palette(
    facts: SceneFacts,
    branch: dict[str, Any],
) -> dict[str, list[str] | str]:
    motif = (
        facts.active_foreshadowing[0]
        if facts.active_foreshadowing
        else "未登记伏笔"
    )
    return {
        "location_anchor": facts.location or "未指定地点",
        "motifs": [motif, branch.get("title") or "无分支标题"],
        "sound": _sensory_sound(facts),
        "texture": _sensory_texture(facts),
        "light": _sensory_light(facts),
        "style_filters": facts.style_constraints or ["克制", "准确", "人物行动优先"],
    }


def build_prose_seed(
    facts: SceneFacts,
    cards: list[CharacterCard],
    branch: dict[str, Any],
    sensory: dict[str, list[str] | str],
) -> list[str]:
    lead = _lead_name(cards)
    location = facts.location or "这个地点"
    goal = facts.scene_goal or "眼前的目标"
    external = facts.external_conflict or "外部阻碍"
    hook = facts.next_hooks[0] if facts.next_hooks else "新的后果"
    premise = branch.get("premise") or "人物必须按自己的逻辑行动"
    sound = _first_sensory(sensory, "sound") or "细小的动静"
    texture = _first_sensory(sensory, "texture") or "发冷的边缘"
    return [
        f"{location} 先给了 {lead} 一个不肯退让的细节：{sound}。{lead} 先停住动作，确认 `{goal}` 会把局面推向哪里。",
        f"`{external}` 没有突然爆发，它只是一步一步逼近。{lead} 伸手碰到{texture}时，旧习惯先一步收紧了他的判断；他避开最顺手的办法，选择了更慢、更难、但仍属于他的路。",
        f"这一版正文种子采用 `{premise}` 的分支前提。结尾不要替读者总结答案，只让 `{hook}` 成为下一场景可以接住的输入。新增事实仍是候选，不能在本场景自动写入 canon。",
    ]


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


def _dialogue_intent(facts: SceneFacts, card: CharacterCard) -> dict[str, str]:
    return {
        "speaker": card.name or card.character_id,
        "wants": _first_nonempty(card.desire + card.intention)
        or facts.scene_goal
        or "推进当前场景目标。",
        "avoids": _first_nonempty(card.fear + card.secret)
        or facts.internal_conflict
        or "避免暴露过多信息。",
        "speech_strategy": card.speech_style or "让语气服务关系压力，少解释，多留白。",
        "forbidden_exposition": "不得借对白直接讲述 background_story；只能让语气、停顿和避词泄露压力。",
    }


def _sensory_sound(facts: SceneFacts) -> list[str]:
    text = " ".join(
        [facts.location, facts.external_conflict, " ".join(facts.active_foreshadowing)]
    )
    if "电" in text:
        return ["断续电流声", "远处脚步被空墙放大"]
    if "雨" in text:
        return ["雨点敲击硬物", "压低的呼吸声"]
    return ["低频环境声", "被刻意压住的脚步或语气"]


def _sensory_texture(facts: SceneFacts) -> list[str]:
    text = facts.location + facts.external_conflict
    if "旧" in text or "档案" in text:
        return ["纸页边缘发脆", "灰尘贴在指腹"]
    if "地下" in text:
        return ["潮湿墙面", "发凉的金属边缘"]
    return ["温度变化", "粗糙边缘", "被反复触碰的物件"]


def _sensory_light(facts: SceneFacts) -> list[str]:
    text = facts.location + facts.external_conflict
    if "停电" in text or "夜" in text:
        return ["低光", "手电余光", "门缝暗影"]
    return ["局部光源", "遮挡形成的阴影", "人物视线避开的亮处"]


def _first_sensory(sensory: dict[str, list[str] | str], key: str) -> str:
    value = sensory.get(key, "")
    if isinstance(value, list):
        return _first_nonempty(value)
    return str(value)


def _lead_name(cards: list[CharacterCard]) -> str:
    return cards[0].name or cards[0].character_id or "核心角色" if cards else "核心角色"


def _first_nonempty(items: list[str]) -> str:
    return next((item for item in items if item), "")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "build_dialogue_intents",
    "build_prose_seed",
    "build_sensory_palette",
    "build_subtext_map",
    "character_payload",
    "flow_gate",
    "guardrails",
    "revision_targets",
    "serializable_branch",
]
