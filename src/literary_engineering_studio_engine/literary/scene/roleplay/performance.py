"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from .relay_context import render_relay_context, validated_knowledge_quotes


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v7"
MAX_BEATS = 4
MAX_ACTOR_ENTRIES = 12
MAX_UNKNOWN_SLOTS = 8


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
) -> str:
    """Ask the main creative model to direct actors without drafting prose."""

    return f"""# Scene Performance Direction

你是本场唯一主创的导演阶段。只确定场景层级的局面和底线，不代演员安排台词、身体动作或回应顺序。beats 是至多 {MAX_BEATS} 个情境锚点：外部局面怎样变化、已确认的事实何时进入人物视野；不是人物轮流发言的格子。不要指定谁说话、说什么、怎样证明、谁先伸手或对手应如何回应。目标和结局已由 SceneBrief 锁定，角色可以自行选择在锚点之间开口、回避、反对、沉默或行动。不写正文，不新增事件。

人物自己的背景、关系、欲望与误判将由人物档案直接提供，环境的可感范围将由 SceneBrief 与来源直接提供。你不要二次改写成 actor_tasks 或 environment_task：那会把你的解释误作角色必须履行的心理任务。不得将文风参考的物件、天气或历史移入本场。

自由属于表达和微观选择，不属于世界事实。不得临场发明钟点、设备读数、未出现的道具、设备部件、旧物或往事；若来源只说“大致顺序”，任务单也只允许大致顺序。不能用“展示性格”“推进剧情”这类空任务。

unknown_slots 只列本场资料尚未确认、但容易被误写成确定事实的少量空位，例如歌曲名、精确钟点、设备型号或关键道具的有无。它是事实留白，不是演员的说话方式、动作要求或情节任务；普通不承担证据作用的感官质感不必逐项禁止。没有这样的空位就返回空数组。

## SceneBrief
{json.dumps(brief, ensure_ascii=False)}

## Expression And Voice
{json.dumps(expression, ensure_ascii=False)}

## Confirmed Sources
{sources[:10_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"与 SceneBrief 相同","beats":[{{"beat_id":"b1","event":"外部局面的已确定变化或人物可感知的新处境；不写任何人的具体言行"}}],"unknown_slots":["尚未确认的具体事实空位；不写风格和动作要求"]}}。
每个参与者都会独立拿到完整场景；你不分配发言、心理任务、环境焦点。不得改变 Canon、人物名单、时间数值、场景结局；不得预写标准台词或环境段落。"""


def parse_performance_plan(payload: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("scene_id") or "") != str(brief.get("scene_id") or ""):
        raise ValueError("performance plan scene_id mismatch")
    beats = payload.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("performance plan requires 1-4 beats")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(beats, 1):
        normalized.append(_parse_beat(item, index))
    if "actor_tasks" in payload or "environment_task" in payload:
        raise ValueError("performance director must not assign actor or environment tasks")
    unknown_slots = _parse_unknown_slots(payload.get("unknown_slots"))
    return {
        "schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "beats": normalized,
        "unknown_slots": unknown_slots,
    }


def _parse_unknown_slots(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_UNKNOWN_SLOTS:
        raise ValueError("performance unknown_slots must be a list of at most eight factual gaps")
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


def render_actor_scene_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], voice: dict[str, Any],
    unknown_slots: list[str] | None = None, *,
    public_log: list[dict[str, Any]] | None = None,
    pending_outcome: str | None = None,
    knowledge_quotes: list[str] | None = None,
    max_entries: int = MAX_ACTOR_ENTRIES,
) -> str:
    speaker = _actor_scene_speaker(beats, str(voice.get("speaker") or ""))
    _validate_actor_prompt_options(beats, public_log, pending_outcome, knowledge_quotes, max_entries)
    person = _actor_identity(voice, speaker)
    state = voice.get("voice_state") if isinstance(voice.get("voice_state"), dict) else {}
    scene = _actor_scene_view(brief, public_log, knowledge_quotes)
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
    opening = (
        "我只从已经发生的公共互动往下活。即使知道场景的方向，也不为完成导演任务而抢先开口；我的下一步由此刻对方真正说过、做过的事触发。"
        if public_log is not None else "我从第一个时刻一直活到最后一个时刻，不在每拍重置自己。"
    )
    epistemic_freedom = (
        "我可以试探、说谎、误记或猜测；这些是我的主观言行，不会因此成为世界事实。"
        "如果谈到尚无来源的细节，不能在自己的未出口念头里把它当成确凿记忆。"
        if public_log is not None else ""
    )
    entry_scope = "本轮接下来的" if public_log is not None else "我整场自然发生的"
    return f"""# 我在场：{person['name']}

{opening}下面给的是我已经身处的境况，不是要照念的台词；导演没有替我分配发言回合。在事实与结果的边界里，我自行决定何时开口、岔开、反问、沉默，做什么或不做什么。我可以在同一时刻说几句，也可以走过一个时刻而没有任何外显反应；不必每拍制造手势或职业解释。

## 我是谁
我的身份：{person['role']}
我相信：{person['belief']}
我想要：{person['wants']}
我避开或害怕：{person['avoids']}
我的底线：{person['moral_line']}
过往在我身上留下的行为痕迹：{json.dumps(person['background_influence'], ensure_ascii=False)}
我平时的说话倾向（不是每句的模板；此刻可偏离）：{json.dumps(person['stable_voice'], ensure_ascii=False)}
我眼前的人、关系、所知与误知：{json.dumps(state, ensure_ascii=False)}

## 我确实置身的场景
{json.dumps(scene, ensure_ascii=False)}

## 我在这场戏里依次经历的时刻
{json.dumps(moments, ensure_ascii=False)}
{relay_context}

## 本场明确留白
{json.dumps(unknown_slots or [], ensure_ascii=False)}
这些空位没有确定答案，不把它们说成已发生或已证实的事实；我仍可用自己的方式避开、怀疑或追问。除此之外，我的语气、停顿、取舍和即时反应由我自己决定。

从自己的冲动出发经历这些时刻，但不把冲动解释给读者。只交我的话与我亲手做的事，不替别人回答。场景锚点不是要我照着演的行动表。{epistemic_freedom}世界事实只从本场已知资料来：不知道具体设备部件、道具、读数或往事时，不能靠职业知识补成现场证据；我的自主性在回应方式，不在创造新的物证。

返回一个 JSON 对象：{output_shape}。entries 是{entry_scope}发言与行为，按时间顺序零至 {max_entries} 项；每项指向发生时最近的 beat_id，同一锚点可有多项，也可没有。private_impulse 写第一人称未出口念头；first_person_action 写第一人称可见动作，没有就留空；spoken 写真正说出口的台词，不带引号或批注，没有就留空。每项至少有一种外显表达。不要为了填满锚点而制造话或动作。"""


def _validate_actor_prompt_options(
    beats: list[dict[str, str]], public_log: list[dict[str, Any]] | None,
    pending_outcome: str | None, knowledge_quotes: list[str] | None, max_entries: int,
) -> None:
    if not 1 <= max_entries <= MAX_ACTOR_ENTRIES:
        raise ValueError("actor scene max_entries is out of range")
    if public_log is None and (pending_outcome is not None or knowledge_quotes is not None):
        raise ValueError("actor relay facts require a public_log")
    if public_log is not None and len(beats) != 1:
        raise ValueError("actor relay requires exactly one current beat")


def _actor_scene_view(
    brief: dict[str, Any], public_log: list[dict[str, Any]] | None, knowledge_quotes: list[str] | None,
) -> dict[str, Any]:
    keys = ("scene_id", "participants", "location", "viewpoint")
    if public_log is None:
        return {key: brief.get(key) for key in (
            "scene_id", "participants", "location", "objective", "canon_constraints", "incoming_handoff", "viewpoint",
        )}
    return {**{key: brief.get(key) for key in keys},
            "confirmed_knowledge": validated_knowledge_quotes(brief, knowledge_quotes or [])}


def _actor_scene_speaker(beats: list[dict[str, str]], speaker: str) -> str:
    if not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("actor scene requires one to four beats")
    if not speaker:
        raise ValueError("actor scene requires a speaker")
    if len({beat["beat_id"] for beat in beats}) != len(beats):
        raise ValueError("actor scene beat_id must be unique")
    return speaker


def _actor_identity(voice: dict[str, Any], fallback_name: str) -> dict[str, Any]:
    stable_voice = voice.get("stable_voice") or voice.get("speech_strategy") or "未提供；不要伪造固定口癖。"
    if isinstance(stable_voice, dict):
        stable_voice = {key: stable_voice.get(key) for key in ("vocabulary", "rhythm", "taboo_words") if stable_voice.get(key)}
    if isinstance(stable_voice, dict) and isinstance(stable_voice.get("rhythm"), str):
        stable_voice["rhythm"] = re.sub(r"[‘“][^’”]+[’”]", "自己的避词", stable_voice["rhythm"])
    return {
        "name": voice.get("speaker") or fallback_name,
        "role": voice.get("role") or "身份未提供；不得自行补造。",
        "belief": voice.get("belief") or "未提供。",
        "wants": voice.get("wants") or "以当前节拍为限。",
        "avoids": voice.get("avoids") or "未提供。",
        "moral_line": voice.get("moral_line") or "未提供。",
        "background_influence": voice.get("background_influence") or [],
        "stable_voice": stable_voice,
    }


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
    if (not values["spoken"] and not values["first_person_action"]) or len(values["spoken"]) > 500 or len(values["first_person_action"]) > 300:
        raise ValueError("actor scene entry requires bounded speech or action")
    if len(values["private_impulse"]) > 160:
        raise ValueError("actor scene private impulse is too long")
    return {"entry_id": f"{speaker}:{number}", "beat_id": beat_id, **values}


def render_environment_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], style_reference: str,
    sources: str, unknown_slots: list[str] | None = None,
) -> str:
    return f"""# Independent Environment Writing

你是本场独立的环境描写写手。主创只给你视角与事实边界，不替你决定看哪一处、用哪种感官、句子怎样起伏。让环境在这个人的可感知范围里发生，而不是填写光、声、气味清单：某处细节可停留，也可一笔带过，不必每句都推进剧情。普通且不承担证据作用的质感可以自由试写；一旦痕迹、器物状态或声音会像线索，就须有来源。只写环境本身，不写人物动作、心理、对白或设备诊断；不增新地点、历史、天气、规则或关键事件，不解释主题。参考选段用于感受表达可能性，不复制原句、专名或特定物件。

## SceneBrief
{json.dumps({key: brief.get(key) for key in ('scene_id', 'objective', 'viewpoint', 'location', 'canon_constraints', 'participants')}, ensure_ascii=False)}

## Moments Available For Environmental Writing
{json.dumps(beats, ensure_ascii=False)}

## Style Reference
{style_reference[:4_000] or '沿用项目当前文风。'}

## Confirmed Sources
{sources[:8_000] or '无额外来源。'}

## 本场明确留白
{json.dumps(unknown_slots or [], ensure_ascii=False)}
不要把这些尚未确认的空位描写成已存在的环境事实或线索；普通、不承担证据作用的感官质感仍由你自由选择。

仅返回 JSON：{{"scene_id":"{brief['scene_id']}","passages":[{{"beat_id":"可用节拍的 beat_id","focal_character":"现有视角人物或空串","description":"独立环境描写，不含人物动作和对白"}}]}}。自行挑真正需要环境语言的位置，返回零至四段；若此场无需独立环境段，就返回空数组。长短由场景决定，每段不超过 350 字。不要附“这段象征什么”的说明，不把参考选段的原句、专名或连续措辞带入本作。"""


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
    if not values["description"] or len(values["description"]) > 350 or len(values["scene_function"]) > 250:
        raise ValueError("environment passage is missing or too long")
    if re.search(r"(?:说|问|答|喊|叫|应|道|开口)\s*[：:]?\s*[“\"]", values["description"]):
        raise ValueError("environment passage contains dialogue")
    return {"beat_id": item["beat_id"], **values}


def render_performance_materials(plan: dict[str, Any], actors: list[dict[str, Any]], environment: dict[str, Any] | None) -> str:
    block = "\n".join((
        "以下是各独立 Agent 的非权威整场表演素材。你是唯一正文作者，负责选取、交错和叙述衔接，但人物所有说出口的话与可见行为须先出现在对应角色 Agent 的 entries 中；不能自行补造角色台词、手势或操作。若素材不足以兑现 SceneBrief，先报告缺口，不以通用对白补齐。同一 speaker 的 entries 来自一轮连续扮演；若与事实相容，保留其称呼、语序、避词和受压变化，不把各人声音润平成中性解释。spoken 是演员的台词原文，first_person_action 是第一人称动作意图、须按正文视角叙述但不得增加动作。private_impulse 与 scene_function 是后台提示，绝不可写入正文。环境候选只提供空间与感知，不得决定人物动作、台词或事实。所有候选都是可拒绝的材料，不是新事实的来源；未经 SceneBrief 或 Relevant Sources 确认的设备部件、操作、数值、物件、线索和往事不得写入正文。",
        json.dumps({"plan": plan, "actor_candidates": actors, "environment_candidates": environment or {}}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 16_000:
        raise ValueError("scene performance material block exceeds prompt budget")
    return block


__all__ = [
    "PERFORMANCE_SCHEMA", "render_performance_plan_prompt", "parse_performance_plan",
    "render_actor_prompt", "render_actor_scene_prompt", "parse_actor_material", "parse_actor_scene_material", "render_environment_prompt",
    "parse_environment_material", "render_performance_materials",
]
