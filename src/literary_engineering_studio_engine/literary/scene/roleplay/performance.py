"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from .actor_personas import DEFAULT_LANGUAGE_STYLE
from .interaction import parse_interaction_direction
from .relay_context import render_relay_context, validated_knowledge_quotes, validated_opening_situation, validated_public_log


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v11"
LITERATURE_STYLE_HEADER = "[LITERATURE_STYLE]"
ACTOR_IMMERSION_REQUIREMENTS = """【角色沉浸要求】在你的思考过程（<think>标签内）中，请遵守以下规则：
1. 请以角色第一人称进行内心独白，用括号包裹内心活动，例如"（心想：……）"或"(内心OS：……)"
2. 用第一人称描写角色的内心感受，例如"我心想""我觉得""我暗自"等
3. 思考内容应沉浸在角色中，通过内心独白分析剧情和规划回复"""
MAX_BEATS = 4
MAX_ACTOR_ENTRIES = 12
ENVIRONMENT_SECTIONS = (
    "【SCENE_LOAD】", "[COMPOSITION_MODE]", "[SCENE_CORE]",
    "[SCENE_SURFACE]", "[LITERATURE_STYLE]", "[NOW_TO_DO]",
)
ENVIRONMENT_INITIALIZATION_EXAMPLE = """【SCENE_LOAD】
SCENE_CLAIM_LANDSCAPE_DESCRIBER
LANG_ZH_CN_ONLY

[COMPOSITION_MODE]
SCENE_RENDER
PERSPECTIVE_COHERENT
TIME_COHERENT
OBSERVATION_AS_INTERPRETATION
NO_PLOT_NO_DIALOGUE

[SCENE_CORE]
ATTR_ATMOSPHERE_WITH_EMOTIONAL_PRESSURE
ATTR_EMOTION_THROUGH_PERCEPTION
ATTR_EMOTIONAL_UNDERTOW_IN_SPACE
ATTR_SELECTIVE_ATTENTION
ATTR_SENSORY_TRANSFORMATION
ATTR_SYMBOLIC_RESONANCE
ATTR_RHYTHMIC_EXPANSION

[SCENE_SURFACE]
ATTR_LYRICAL_VARIATION
ATTR_IMAGE_ASSOCIATION
ATTR_SPACIOUS_CADENCE
ATTR_PERSPECTIVE_ATTUNED
ATTR_EMOTIONAL_TIDE_IN_CADENCE

[LITERATURE_STYLE]
LITERARY_TEXTURE
MOVEMENT_SYMBOLISM
CADENCE_LYRICAL_VARIATION

[NOW_TO_DO]
STAND_BY
WAIT_FOR_DETAIL"""


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
) -> str:
    """Ask the main creative model to direct actors without drafting prose."""

    actor_prompts = {str(name): (
        "【PERSONA_LOAD】\nSELF_CLAIM_ROMANIZED_NAME\nLANG_ZH_CN_ONLY\n\n"
        "【PERSONALITY_CORE】\nTRAIT_OWN_ARCHETYPE\nTRAIT_INNER_CONTRADICTION\nEMOTION_RELATIONALLY_ALIVE\nEMOTION_OWN_CONTRADICTION\n\n"
        "【PERSONALITY_PUBLIC】\nTRAIT_VISIBLE_PERSONALITY\n\n"
        "[LANGUAGE_STYLE]\n" + "\n".join(DEFAULT_LANGUAGE_STYLE) + "\nVOICE_RELATIONAL_TEMPERAMENT\n\n"
        "[LITERATURE_STYLE]\nAUTHOR_LIKE_SOMEBODY\nMOVEMENT_STYLE_SOMESTYLE\nCADENCE_OWN_LITERARY_RHYTHM"
    ) for name in brief.get("participants") or ()}
    actor_tasks = {str(name): "此人的兴趣、与他人的关系、眼前已知的事和仍可自行决定的事" for name in brief.get("participants") or ()}
    opening_example = {
        "finish": not bool(actor_prompts), "next_speaker": next(iter(actor_prompts), ""),
        "beat_id": "b1" if actor_prompts else "", "scene_change": "开场进入的已确认变化" if actor_prompts else "",
        "cue": "此人主要面对谁、凭什么开口、关系压力何在" if actor_prompts else "", "director_note": "留给主创正文的判断" if actor_prompts else "",
    }
    return f"""# Scene Performance Direction

你是本场主创。从人物档案、关系和过往选择中辨认每人的鲜明性格与说话气质。选型时可参考几类标签：性格与心理（如傲娇、腹黑、毒舌、元气、敏感），外显气质与已确认的形象，稳定身份或种族，长期关系与互动方式，以及作品适用的亚文化人物原型。每人通常挑三到五个能彼此作用的核心人设标签，形成这个人物自己的组合；外貌、年龄、身份、关系须以已确认设定为依据。尤其想清楚此人怎样听人说话、怎样开玩笑、在谁面前会改变声调。叙事职能、本场任务与具体动作进入后续场景资料。

用简短、抽象的英文大写标签写 actor_prompts：PERSONA_LOAD 写姓名与稳定身份；PERSONALITY_CORE 写鲜明的人格原型、内心反差和此人特有的情绪运动。用一两项有辨识度的 EMOTION_ 标签写出他如何渴望、羞恼、依恋、嫉妒或掩饰，例如 EMOTION_FIERCE_TENDERNESS、EMOTION_PRIDE_OVER_LONGING；每个人的组合应有自己的情绪温度。PERSONALITY_PUBLIC 写别人实际感受到的气质。[LANGUAGE_STYLE] 保留 ANTI_PLAIN、POLISHED、ANTI_SHORT_SENTENCES，再以一两项 VOICE_ 概括此人面对人的口头气质，例如 VOICE_SLY_AFFECTION、VOICE_VOLUBLE_TENDERNESS、VOICE_WRY_FLIRTATION。让气质在玩笑、受伤、求助与争执时各有变化。[LITERATURE_STYLE] 是主要风格指向，选择统摄修辞、句法运动与情绪声调的作家、文学流派及抽象文学节奏；让这一层比其余标签更鲜明。区块和字段数量可自由调整。示例占位标签换成该人物自己的标签。已保存的 actor_personas 是既有人设素材；角色沉浸要求由初始化渲染器统一附加。

actor_tasks 给此人一个有生活感的起点：他认识谁、误会谁、想靠近或躲开谁，写稳定的关系与内在兴趣，供主创安排轮次；临场信息由 opening_direction 与后续 direction 承载。beats 承载外部情势的变化，轮间 direction 交给演员新的关系压力与行动余地。人格和口头气质标签应当换一个场景仍然成立；职业、器物、流程、计数习惯和本场职能放在经历或后续局面里。情绪变化时同一人的句子可改换长度与走向；具体台词、手势和临场反应由演员自己选择。每条标签只由大写英文字母和下划线组成：姓名转写成大写拼音（如 SELF_CLAIM_XU_YAO）。

不要把 PLAIN、SHORT、CLIPPED、COUNTED、ACCOUNTING、INVENTORY、MINIMAL 等平淡、惜字、清单或计数取向写成 VOICE_、MOVEMENT_、CADENCE_ 标签。

environment_initialization 是独立环境 Agent 的首条消息。保留示例的六个区块名；标签只定性长期适用的观察、构图、感官转化、意象关联、情绪在空间中的渗透和语言节奏等抽象技法。[SCENE_CORE] 与 [SCENE_SURFACE] 用鲜明的 ATTR_EMOTION_ 或 ATTR_EMOTIONAL_ 标签确定这部作品特有的情绪空间感，例如 ATTR_EMOTION_AS_UNSETTLED_SPACE、ATTR_EMOTIONAL_TIDE_IN_CADENCE。每区按作品气质自由增删改，数量不限；[LITERATURE_STYLE] 可用作家、文学流派或作品的抽象文学倾向。标签用英文大写字母、数字与下划线。具体天气、光线、物件、地点、颜色、动作和某一场的意象放到后续场景资料里；初始化避免白描、直描、写实主义、克制简短等使环境段落变平的定性标签。

人物情绪组合例如傲娇与依恋，宜从已确认关系和欲望中生长；情绪标签应鲜明，且与各人的欲望、羞耻和亲疏关系相配。

## Environment Initialization Example
{ENVIRONMENT_INITIALIZATION_EXAMPLE}

beats 是至多 {MAX_BEATS} 个外部情境变化，从已知场地、人物和事件自然生长，使下一轮人物的关系或选择余地发生变化。opening_direction 同时决定第一轮由谁回应、使用哪个 beat 以及此人当下可感的局面；cue 写清主要对话对象、可感的起因和关系压力，让演员自己决定声音和动作。第一轮公开舞台为空，请把触发事件的前因排通：若误称来自另一人的玩笑或暗示，先让玩笑者亲自演出，使后来的角色真能听见并误解；若误称者自己挑起话头，给他可感、可信的误认依据和明确的对话对象。若 SceneBrief 已指定某人说出关键称呼或完成情节触发行为，把这个必须发生的情节事实交给该人物本人的 cue，留其余措辞、语气和反应由他创作；下一轮才让别人回应。beats 与 scene_change 承载环境、物件或已演言行的外部后果；若一人的关键言行构成另一人回应的前因，先让前者获得自己的轮次。即使大局需要多人相遇，也可以让一次玩笑、误听或好奇慢慢牵出下一人，人物各自保有不说往事的权利。若本场没有参与人物，opening_direction.finish 为 true。已确认的场景结果仍须成立；结果之间的互动路径可由演员发现。unknown_slots 记录容易误写为事实的资料空位，没有就返回空数组。你在这里设计人物声音与局面。

## SceneBrief
{json.dumps(brief, ensure_ascii=False)}

## Expression And Voice
{json.dumps(expression, ensure_ascii=False)}

## Confirmed Sources
{sources[:10_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"与 SceneBrief 相同","beats":[{{"beat_id":"b1","event":"已确认的外部变化"}}],"opening_direction":{json.dumps(opening_example, ensure_ascii=False)},"actor_prompts":{json.dumps(actor_prompts, ensure_ascii=False)},"actor_tasks":{json.dumps(actor_tasks, ensure_ascii=False)},"environment_initialization":{json.dumps(ENVIRONMENT_INITIALIZATION_EXAMPLE, ensure_ascii=False)},"unknown_slots":[]}}。两组人物键已经列全；人物事实以档案和来源为准。"""


def parse_performance_plan(payload: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("scene_id") or "") != str(brief.get("scene_id") or ""):
        raise ValueError("performance plan scene_id mismatch")
    beats = payload.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("performance plan requires 1-4 beats")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(beats, 1):
        normalized.append(_parse_beat(item, index))
    if "environment_task" in payload:
        raise ValueError("performance director must not assign an environment task")
    participants = [str(name) for name in brief.get("participants") or ()]
    prompts = _parse_actor_plan_map(payload, "actor_prompts", participants)
    tasks = _parse_actor_plan_map(payload, "actor_tasks", participants)
    opening = parse_interaction_direction(payload.get("opening_direction"), brief, {"beats": normalized})
    if participants and opening["finish"]:
        raise ValueError("performance opening_direction must begin with a participant")
    environment_initialization = parse_environment_initialization(payload.get("environment_initialization"))
    unknown_slots = _parse_unknown_slots(payload.get("unknown_slots"))
    return {
        "schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "beats": normalized,
        "actor_prompts": prompts, "actor_tasks": tasks, "opening_direction": opening,
        "environment_initialization": environment_initialization, "unknown_slots": unknown_slots,
    }


def parse_environment_initialization(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("environment_initialization must be a six-section tag message")
    lines = [line.strip() for line in value.strip().splitlines() if line.strip()]
    headers = [line for line in lines if line.startswith("[") or line.startswith("【")]
    if not lines or lines[0] != ENVIRONMENT_SECTIONS[0] or headers != list(ENVIRONMENT_SECTIONS):
        raise ValueError("environment_initialization requires the six scene sections in order")
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", line) for line in lines if line not in ENVIRONMENT_SECTIONS):
        raise ValueError("environment_initialization tags must use uppercase letters, digits, and underscores")
    mounted = value.strip()
    if not any(line.startswith(("ATTR_EMOTION_", "ATTR_EMOTIONAL_")) for line in lines):
        mounted = mounted.replace("[SCENE_CORE]", "[SCENE_CORE]\nATTR_EMOTION_THROUGH_PERCEPTION", 1)
    return mounted


def _parse_actor_plan_map(payload: dict[str, Any], field: str, participants: list[str]) -> dict[str, str]:
    values = payload.get(field)
    if not isinstance(values, dict) or set(values) != set(participants):
        raise ValueError(f"performance {field} must cover every participant")
    if any(not isinstance(values[name], str) or not values[name].strip() or len(values[name]) > 2000 for name in participants):
        raise ValueError(f"performance {field} must contain one bounded prompt per participant")
    return {name: values[name].strip() for name in participants}


def _parse_unknown_slots(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("performance unknown_slots must be a list of factual gaps")
    slots = []
    for item in value:
        if not isinstance(item, str) or not 2 <= len(item.strip()) <= 120:
            raise ValueError("performance unknown_slots must contain bounded text")
        slots.append(item.strip())
    if len(set(slots)) != len(slots):
        raise ValueError("performance unknown_slots must be distinct")
    return slots


def _parse_beat(item: Any, index: int) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("beat_id") != f"b{index}":
        raise ValueError("performance beat_id must be sequential")
    if any(key in item for key in ("speaker", "speech_act", "information", "action_boundary", "response_boundary", "environment_need")):
        raise ValueError("performance beat must not script character speech or action")
    event = str(item.get("event") or "").strip()
    if not event or len(event) > 300:
        raise ValueError("performance beat requires a bounded event")
    return {"beat_id": f"b{index}", "event": event}


def render_actor_prompt(
    brief: dict[str, Any], beat: dict[str, str], voice: dict[str, Any],
) -> str:
    """Render a single-beat convenience prompt using the current scene contract."""

    return render_actor_scene_prompt(brief, [beat], {**voice, "speaker": voice.get("speaker") or beat.get("speaker") or ""})


def render_actor_initialization_prompt(voice: dict[str, Any]) -> str:
    """Keep the director-authored English persona tags as the first message."""

    name = str(voice.get("name") or voice.get("speaker") or "").strip()
    persona = str(voice.get("roleplay_direction") or "").strip()
    if not name or not persona:
        raise ValueError("actor initialization requires name and persona direction")
    style_header = "[LANGUAGE_STYLE]"
    headers = ("【PERSONA_LOAD】", "【PERSONALITY_CORE】", "【PERSONALITY_PUBLIC】", style_header, LITERATURE_STYLE_HEADER)
    if not persona.startswith(headers[0]) or any(header not in persona for header in headers[1:3]):
        raise ValueError("actor initialization requires the three persona sections")
    if any(not re.fullmatch(r"[A-Z_]+", line) for line in persona.splitlines() if line and line not in headers):
        raise ValueError("actor initialization tags must use uppercase English letters and underscores")
    mounted = _mount_default_language_style(persona, style_header)
    mounted = _mount_default_emotion(mounted)
    if LITERATURE_STYLE_HEADER not in mounted.splitlines():
        mounted += f"\n\n{LITERATURE_STYLE_HEADER}"
    return f"{mounted}\n\n{ACTOR_IMMERSION_REQUIREMENTS}"


def _mount_default_emotion(persona: str) -> str:
    if any(line.startswith("EMOTION_") for line in persona.splitlines()):
        return persona
    return persona.replace("【PERSONALITY_CORE】", "【PERSONALITY_CORE】\nEMOTION_RELATIONALLY_ALIVE", 1)


def _mount_default_language_style(persona: str, style_header: str) -> str:
    if style_header not in persona.splitlines():
        block = f"{style_header}\n" + "\n".join(DEFAULT_LANGUAGE_STYLE)
        if LITERATURE_STYLE_HEADER in persona.splitlines():
            return persona.replace(LITERATURE_STYLE_HEADER, f"{block}\n\n{LITERATURE_STYLE_HEADER}", 1)
        return f"{persona}\n\n{block}"
    before, after = persona.split(style_header, 1)
    style_tags = after.splitlines()
    missing = [tag for tag in DEFAULT_LANGUAGE_STYLE if tag not in style_tags]
    return before + style_header + ("\n" + "\n".join(missing) if missing else "") + after


def render_actor_scene_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], voice: dict[str, Any],
    unknown_slots: list[str] | None = None, *,
    public_log: list[dict[str, Any]] | None = None,
    pending_outcome: str | None = None,
    knowledge_quotes: list[str] | None = None,
    opening_situation: str | None = None,
    max_entries: int = MAX_ACTOR_ENTRIES,
) -> str:
    speaker = _actor_scene_speaker(beats, str(voice.get("speaker") or ""))
    _validate_actor_prompt_options(beats, public_log, pending_outcome, knowledge_quotes, opening_situation, max_entries)
    person = _actor_identity(voice, speaker)
    state = voice.get("voice_state") if isinstance(voice.get("voice_state"), dict) else {}
    scene = _actor_scene_view(brief, public_log, knowledge_quotes, opening_situation)
    moments = [{"beat_id": beat["beat_id"], "event": beat["event"]} for beat in beats]
    output_shape = json.dumps({
        "scene_id": brief["scene_id"], "speaker": speaker,
        "entries": [{
            "beat_id": beats[0]["beat_id"],
            "private_impulse": "",
            "first_person_action": "",
            "spoken": "",
        }],
    }, ensure_ascii=False)
    relay_context = render_relay_context(brief, public_log, pending_outcome) if public_log is not None else ""
    entry_scope = "本轮接下来的" if public_log is not None else "我整场自然发生的"
    return f"""# 本场角色任务单

主创交给我处理的场景职责：{voice.get('scene_task') or '在已给出的场景变化中，以人物自己的方式作出反应。'}
我从这一场的开头经历到结束，自行选择何时说话、怎样回应或沉默。给出整场属于我的发言与可见行为，供主创组织正文。

## 我的处境与已知事实
我相信：{person['belief']}
我想要：{person['wants']}
我避开或害怕：{person['avoids']}
我的底线：{person['moral_line']}
过往给我的行为留下的痕迹：{json.dumps(person['background_influence'], ensure_ascii=False)}
我亲历的往事：{json.dumps(person['lived_history'], ensure_ascii=False)}
我眼前的人、关系、所知与误知：{json.dumps(state, ensure_ascii=False)}

## 场景情况
{json.dumps(scene, ensure_ascii=False)}

## 依次发生的情境变化
{json.dumps(moments, ensure_ascii=False)}
{relay_context}

## 尚未确认的事实
{json.dumps(unknown_slots or [], ensure_ascii=False)}

场景结果由主创任务单确定，抵达结果的说法和行为由我选择。未知资料可以成为猜测。

## 交付格式
返回一个 JSON 对象：{output_shape}。entries 是{entry_scope}发言与行为，按时间顺序零至 {max_entries} 项，每项标记最近的 beat_id；同一时刻可有几项。private_impulse 是未出口的第一人称感受，first_person_action 是我做的可见动作，spoken 是我说出的原话。没有的字段留空。"""


def _validate_actor_prompt_options(
    beats: list[dict[str, str]], public_log: list[dict[str, Any]] | None,
    pending_outcome: str | None, knowledge_quotes: list[str] | None,
    opening_situation: str | None, max_entries: int,
) -> None:
    if not 1 <= max_entries <= MAX_ACTOR_ENTRIES:
        raise ValueError("actor scene max_entries is out of range")
    if public_log is None and (pending_outcome is not None or knowledge_quotes is not None or opening_situation is not None):
        raise ValueError("actor relay facts require a public_log")
    if public_log is not None and len(beats) != 1:
        raise ValueError("actor relay requires exactly one current beat")


def _actor_scene_view(
    brief: dict[str, Any], public_log: list[dict[str, Any]] | None, knowledge_quotes: list[str] | None,
    opening_situation: str | None,
) -> dict[str, Any]:
    keys = ("scene_id", "participants", "location", "viewpoint")
    if public_log is None:
        return {key: brief.get(key) for key in (
            "scene_id", "participants", "location", "objective", "canon_constraints", "incoming_handoff", "viewpoint",
        )}
    return {**{key: brief.get(key) for key in keys},
            "opening_situation": validated_opening_situation(brief, opening_situation) if opening_situation is not None else "",
            "confirmed_knowledge": validated_knowledge_quotes(brief, knowledge_quotes or []),
            "unplayed_conflict_pressure": brief.get("external_conflict") or ""}


def _actor_scene_speaker(beats: list[dict[str, str]], speaker: str) -> str:
    if not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("actor scene requires one to four beats")
    if not speaker:
        raise ValueError("actor scene requires a speaker")
    if len({beat["beat_id"] for beat in beats}) != len(beats):
        raise ValueError("actor scene beat_id must be unique")
    return speaker


def _actor_identity(voice: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    return {
        "name": voice.get("speaker") or fallback_name,
        "role": voice.get("role") or "身份未提供；不得自行补造。",
        "belief": voice.get("belief") or "未提供。",
        "wants": voice.get("wants") or "以当前节拍为限。",
        "avoids": voice.get("avoids") or "未提供。",
        "moral_line": voice.get("moral_line") or "未提供。",
        "background_influence": voice.get("background_influence") or [],
        "lived_history": _lived_history(voice),
    }


def _lived_history(voice: dict[str, Any]) -> dict[str, Any]:
    value = voice.get("lived_history")
    return value if isinstance(value, dict) else {}


def parse_actor_material(payload: dict[str, Any], beat: dict[str, str]) -> dict[str, Any]:
    if payload.get("beat_id") != beat["beat_id"] or payload.get("speaker") != beat["speaker"]:
        raise ValueError("actor material target mismatch")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 2:
        raise ValueError("actor material requires one or two candidates")
    normalized = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("actor candidate must be an object")
        values = {key: str(item.get(key) or "").strip() for key in ("spoken", "first_person_action", "private_impulse")}
        if (not values["spoken"] and not values["first_person_action"]) or len(values["spoken"]) > 300 or len(values["first_person_action"]) > 220:
            raise ValueError("actor candidate dialogue/action is missing or too long")
        if len(values["private_impulse"]) > 160:
            raise ValueError("actor candidate private impulse is too long")
        normalized.append(values)
    return {"schema": PERFORMANCE_SCHEMA, "beat_id": beat["beat_id"], "speaker": beat["speaker"], "candidates": normalized}


def parse_actor_scene_material(
    payload: dict[str, Any], brief: dict[str, Any], beats: list[dict[str, str]], speaker: str | None = None,
    *, max_entries: int = MAX_ACTOR_ENTRIES,
) -> dict[str, Any]:
    speaker = _actor_scene_speaker(beats, speaker or str(payload.get("speaker") or ""))
    if speaker not in set(brief.get("participants") or ()):
        raise ValueError("actor scene speaker is outside scene participants")
    if payload.get("scene_id") != brief.get("scene_id") or payload.get("speaker") != speaker:
        raise ValueError("actor scene target mismatch")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not 1 <= max_entries <= MAX_ACTOR_ENTRIES or len(entries) > max_entries:
        raise ValueError("actor scene entries must be a bounded list")
    beat_positions = {beat["beat_id"]: index for index, beat in enumerate(beats)}
    normalized: list[dict[str, str]] = []
    previous_position = -1
    for item in entries:
        entry = _parse_actor_scene_entry(item, beat_positions, previous_position, speaker, len(normalized) + 1)
        previous_position = beat_positions[entry["beat_id"]]
        normalized.append(entry)
    return {"schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "speaker": speaker, "entries": normalized}


def _parse_actor_scene_entry(
    item: Any, beat_positions: dict[str, int], previous_position: int, speaker: str, number: int,
) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("actor scene entry must be an object")
    beat_id = str(item.get("beat_id") or "")
    if beat_id not in beat_positions or beat_positions[beat_id] < previous_position:
        raise ValueError("actor scene entries must follow known beats in order")
    values = {key: str(item.get(key) or "").strip() for key in ("spoken", "first_person_action", "private_impulse")}
    if not values["spoken"] and not values["first_person_action"]:
        raise ValueError("actor scene entry requires speech or action")
    return {"entry_id": f"{speaker}:{number}", "beat_id": beat_id, **values}


def render_environment_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], style_reference: str,
    sources: str, unknown_slots: list[str] | None = None,
    *, public_log: list[dict[str, Any]] | None = None, creator_cue: str = "",
) -> str:
    scene_keys = ("scene_id", "viewpoint", "location", "canon_constraints", "participants")
    if public_log is None:
        scene_keys = ("scene_id", "objective", "viewpoint", "location", "canon_constraints", "participants")
    observed = (
        "\n## 此前真正发生的公共言行\n"
        + json.dumps(validated_public_log(brief, public_log[-24:]), ensure_ascii=False)
        + "\n这些人物言行可帮助选择环境描写的时刻。\n"
        if public_log is not None else ""
    )
    return f"""# Independent Environment Writing

沿用你的初始化方式，把情绪与感官观察一起带入本场。

这场的空间、人物位置和已发生言行见下方资料。沿用初始化中的情绪空间标签，让光声、温度、距离和物象承受人物当下的情绪张力；同一空间可随人物注意力转移显出不同情绪。自行选择值得停留的观察时刻、段落长短和语言节奏。场景事实和线索以来源为准；普通感官细节可以自由选择。写出可供主创取舍的环境段落。人物言行只帮助你确定观察时刻；description 集中写空间、光声气息、物象关联和时间的质地，不代替角色续演动作或台词。

## SceneBrief
{json.dumps({key: brief.get(key) for key in scene_keys}, ensure_ascii=False)}

## Moments Available For Environmental Writing
{json.dumps(beats, ensure_ascii=False)}
{observed}

{f'## Current Creator Request: {creator_cue}' if creator_cue else ''}

## Style Reference
{style_reference[:4_000] or '沿用项目当前文风。'}

## Confirmed Sources
{sources[:8_000] or '无额外来源。'}

## 本场明确留白
{json.dumps(unknown_slots or [], ensure_ascii=False)}

仅返回 JSON：{{"scene_id":"{brief['scene_id']}","passages":[{{"beat_id":"可用节拍的 beat_id","focal_character":"现有视角人物或空串","description":"环境段落"}}]}}。自行决定在哪些时刻写，零至四段，每段不超过 600 字。"""


def parse_environment_material(payload: dict[str, Any], brief: dict[str, Any], beats: list[dict[str, str]]) -> dict[str, Any]:
    if payload.get("scene_id") != brief.get("scene_id"):
        raise ValueError("environment material scene_id mismatch")
    passages = payload.get("passages")
    if not isinstance(passages, list) or len(passages) > MAX_BEATS:
        raise ValueError("environment material requires zero to four passages")
    ids = {item["beat_id"] for item in beats}
    focal_options = {str(value) for value in (*(brief.get("participants") or ()), brief.get("viewpoint", "")) if value}
    normalized = [_parse_environment_passage(item, ids, focal_options) for item in passages]
    return {"schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "passages": normalized}


def _parse_environment_passage(item: Any, ids: set[str], focal_options: set[str]) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("beat_id") not in ids:
        raise ValueError("environment passage references unknown beat")
    values = {key: str(item.get(key) or "").strip() for key in ("focal_character", "description", "scene_function")}
    if values["focal_character"] and values["focal_character"] not in focal_options:
        raise ValueError("environment focal character is outside scene participants")
    if not values["description"] or len(values["description"]) > 600 or len(values["scene_function"]) > 250:
        raise ValueError("environment passage is missing or too long")
    if re.search(r"(?:说|问|答|喊|叫|应|道|开口)\s*[：:]?\s*[“\"]", values["description"]):
        raise ValueError("environment passage contains dialogue")
    return {"beat_id": item["beat_id"], **values}


def render_performance_materials(
    plan: dict[str, Any], actors: list[dict[str, Any]], environment: dict[str, Any] | None, *, viewpoint: str = "",
) -> str:
    visible_actors = [
        {**actor, "entries": [{**entry, "private_impulse": ""} for entry in actor.get("entries", [])]}
        if viewpoint and actor.get("speaker") != viewpoint else actor for actor in actors
    ]
    block = "\n".join((
        "以下是各独立 Agent 的整场素材。你是唯一正文作者：选取、交错、修订，亲自写心理、情绪、环境与句法的起伏。演员已生成各自的发言回合和可见行为；你可以改台词的措辞与语势，保留人物之间不同的语言趣味，也可以舍弃候选。private_impulse 可供当前视角的内心书写参考，环境候选可延展为段落。需要新增一轮言行时，请让相应演员先生成。",
        json.dumps({"plan": plan, "actor_candidates": visible_actors, "environment_candidates": environment or {}}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 16_000:
        raise ValueError("scene performance material block exceeds prompt budget")
    return block


__all__ = [
    "PERFORMANCE_SCHEMA", "render_performance_plan_prompt", "parse_performance_plan",
    "render_actor_prompt", "render_actor_initialization_prompt", "render_actor_scene_prompt", "parse_actor_material", "parse_actor_scene_material", "render_environment_prompt",
    "parse_environment_material", "render_performance_materials",
]
