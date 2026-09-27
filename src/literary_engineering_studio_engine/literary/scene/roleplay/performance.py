"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from literary_engineering_studio_engine.prompting.layers import prompt_layer_spec, render_prompt_template

from .actor_personas import DEFAULT_LANGUAGE_STYLE
from .interaction import parse_interaction_direction
from .relay_context import render_relay_context, validated_knowledge_quotes, validated_opening_situation, validated_public_log


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v11"
LITERATURE_STYLE_HEADER = "[LITERATURE_STYLE]"
ACTOR_IMMERSION_REQUIREMENTS = prompt_layer_spec("scene.actor.immersion.protocol").default_text
MAX_BEATS = 4
MAX_ACTOR_ENTRIES = 12
ENVIRONMENT_SECTIONS = (
    "【SCENE_LOAD】", "[COMPOSITION_MODE]", "[SCENE_CORE]",
    "[SCENE_SURFACE]", "[LITERATURE_STYLE]", "[NOW_TO_DO]",
)
ENVIRONMENT_INITIALIZATION_EXAMPLE = prompt_layer_spec("scene.environment.initialization.example").default_text


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
    creative_intent: str = "",
    literary_guidance: str = "",
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
    return render_prompt_template("scene.performance.plan.protocol", (
        ENVIRONMENT_INITIALIZATION_EXAMPLE,
        MAX_BEATS,
        json.dumps(brief, ensure_ascii=False),
        creative_intent or '主创尚未声明；规划时同时考虑人物展示、日常、趣味、留白、误导与节奏。',
        literary_guidance or prompt_layer_spec("scene.performance.plan").default_text,
        json.dumps(expression, ensure_ascii=False),
        sources[:10000] or '无额外来源。',
        json.dumps(opening_example, ensure_ascii=False),
        json.dumps(actor_prompts, ensure_ascii=False),
        json.dumps(actor_tasks, ensure_ascii=False),
        json.dumps(ENVIRONMENT_INITIALIZATION_EXAMPLE, ensure_ascii=False),
    ))


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
    return render_prompt_template("scene.actor.scene.protocol", (
        voice.get('scene_task') or '在已给出的场景变化中，以人物自己的方式作出反应。',
        person['belief'],
        person['wants'],
        person['avoids'],
        person['moral_line'],
        json.dumps(person['background_influence'], ensure_ascii=False),
        json.dumps(person['lived_history'], ensure_ascii=False),
        json.dumps(state, ensure_ascii=False),
        json.dumps(scene, ensure_ascii=False),
        json.dumps(moments, ensure_ascii=False),
        relay_context,
        json.dumps(unknown_slots or [], ensure_ascii=False),
        output_shape,
        entry_scope,
        max_entries,
    ))


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
    literary_guidance: str = "",
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
    return render_prompt_template("scene.environment.turn.protocol", (
        json.dumps({key: brief.get(key) for key in scene_keys}, ensure_ascii=False),
        json.dumps(beats, ensure_ascii=False),
        observed,
        f'## Current Creator Request: {creator_cue}' if creator_cue else '',
        style_reference[:4000] or '沿用项目当前文风。',
        sources[:8000] or '无额外来源。',
        json.dumps(unknown_slots or [], ensure_ascii=False),
        brief['scene_id'],
        literary_guidance or prompt_layer_spec("scene.environment.turn").default_text,
    ))


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
