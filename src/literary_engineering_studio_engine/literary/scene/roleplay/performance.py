"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
import re
from typing import Any


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v5"
MAX_BEATS = 4
MAX_ACTOR_ENTRIES = 12


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
) -> str:
    """Ask the main creative model to direct actors without drafting prose."""

    return f"""# Scene Performance Direction

你是本场唯一主创的导演阶段。只确定场景层级的局面和底线，不代演员安排台词、身体动作或回应顺序。beats 是至多 {MAX_BEATS} 个情境锚点：外部局面怎样变化、已确认的事实何时进入人物视野；不是人物轮流发言的格子。不要指定谁说话、说什么、怎样证明、谁先伸手或对手应如何回应。目标和结局已由 SceneBrief 锁定，角色可以自行选择在锚点之间开口、回避、反对、沉默或行动。不写正文，不新增事件。

actor_tasks 只从现有人物背景、关系与本场压力写每个人的私人牵挂、已知关系或误判。不要规定口吻、词语、句式、动作和态度，也不要把必须交代的剧情事实都塞进角色口中。不同人物的压力必须来自各自已知事实，不套同一套标签。environment_task 只给视角可感范围和未知事实边界；环境写手自行决定关注什么、是否写、停留多久、语言怎样运动。不得将文风参考的物件、天气或历史移入本场。

自由属于表达和微观选择，不属于世界事实。不得临场发明钟点、设备读数、未出现的道具、设备部件、旧物或往事；若来源只说“大致顺序”，任务单也只允许大致顺序。不能用“展示性格”“推进剧情”这类空任务。

## SceneBrief
{json.dumps(brief, ensure_ascii=False)}

## Expression And Voice
{json.dumps(expression, ensure_ascii=False)}

## Confirmed Sources
{sources[:10_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"与 SceneBrief 相同","beats":[{{"beat_id":"b1","event":"外部局面的已确定变化或人物可感知的新处境；不写任何人的具体言行"}}],"actor_tasks":[{{"speaker":"participants 中一人的精确字符串","personal_pressure":"现有人物事实在本场形成的私人牵挂；写其处境，不写该怎么做","relationship_misread":"面对其他参与者的已知关系或误判；没有则留空"}}],"environment_task":{{"focus_beats":["b1"],"focal_condition":"既有视角此刻可感知的范围与来由","perception_boundary":"尚未确认、不能写成事实的空间细节"}}}}。
actor_tasks 必须覆盖全部 participants，顺序不限；每人都会拿到完整场景，不要在 beats 中预分配发言。environment_task 只标感知范围和未知边界，不自行补写空间事实；已确认空间以来源为准。环境节拍只能选自 beats。不得改变 Canon、人物名单、时间数值、场景结局；不得预写标准台词或环境段落。"""


def parse_performance_plan(payload: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("scene_id") or "") != str(brief.get("scene_id") or ""):
        raise ValueError("performance plan scene_id mismatch")
    beats = payload.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("performance plan requires 1-4 beats")
    participants = set(brief.get("participants") or ())
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(beats, 1):
        normalized.append(_parse_beat(item, index))
    actor_tasks = _parse_actor_tasks(payload.get("actor_tasks"), participants)
    environment_task = _parse_environment_task(payload.get("environment_task"), normalized)
    return {
        "schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "beats": normalized,
        "actor_tasks": actor_tasks, "environment_task": environment_task,
    }


def _parse_actor_tasks(value: Any, participants: set[str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) != len(participants):
        raise ValueError("performance actor_tasks must cover scene participants")
    tasks = []
    for item in value:
        if not isinstance(item, dict) or item.get("speaker") not in participants:
            raise ValueError("performance actor task speaker mismatch")
        speaker = item["speaker"]
        fields = ("personal_pressure", "relationship_misread")
        task = {key: str(item.get(key) or "").strip() for key in fields}
        if not task["personal_pressure"] or any(len(text) > 220 for text in task.values()):
            raise ValueError("performance actor task requires bounded pressure")
        tasks.append({"speaker": speaker, **task})
    if len({task["speaker"] for task in tasks}) != len(participants):
        raise ValueError("performance actor_tasks must have unique participants")
    return tasks


def _parse_environment_task(value: Any, beats: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("performance environment_task is missing")
    focus = value.get("focus_beats")
    valid_ids = {beat["beat_id"] for beat in beats}
    if not isinstance(focus, list) or not focus or len(focus) > MAX_BEATS or len(set(focus)) != len(focus) or any(item not in valid_ids for item in focus):
        raise ValueError("performance environment focus_beats must reference distinct beats")
    fields = ("focal_condition", "perception_boundary")
    task = {key: str(value.get(key) or "").strip() for key in fields}
    if not task["focal_condition"] or any(len(text) > 220 for text in task.values()):
        raise ValueError("performance environment_task requires bounded scene-specific cues")
    return {"focus_beats": focus, **task}


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

    return render_actor_scene_prompt(brief, [beat], voice, {"speaker": beat.get("speaker") or voice.get("speaker") or ""})


def render_actor_scene_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], voice: dict[str, Any],
    task: dict[str, str] | None = None,
) -> str:
    speaker = _actor_scene_speaker(beats, str((task or {}).get("speaker") or voice.get("speaker") or ""))
    person = _actor_identity(voice, speaker)
    state = voice.get("voice_state") if isinstance(voice.get("voice_state"), dict) else {}
    scene = {key: brief.get(key) for key in (
        "scene_id", "participants", "location", "objective", "canon_constraints", "incoming_handoff", "viewpoint",
    )}
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
    current_pressure = str((task or {}).get("personal_pressure") or "眼前事件与我既有欲望之间的压力，由我自己体会。")
    relationship_misread = str((task or {}).get("relationship_misread") or "只按我已知的关系与误判行事。")
    return f"""# 我在场：{person['name']}

我从第一个时刻一直活到最后一个时刻，不在每拍重置自己。下面给的是我已经身处的境况，不是要照念的台词；导演没有替我分配发言回合。在事实与结果的边界里，我自行决定何时开口、岔开、反问、沉默，做什么或不做什么。我可以在同一时刻说几句，也可以走过一个时刻而没有任何外显反应；不必每拍制造手势或职业解释。

## 我是谁
我的身份：{person['role']}
我相信：{person['belief']}
我想要：{person['wants']}
我避开或害怕：{person['avoids']}
我的底线：{person['moral_line']}
过往在我身上留下的行为痕迹：{json.dumps(person['background_influence'], ensure_ascii=False)}
我的稳定说话方式：{json.dumps(person['stable_voice'], ensure_ascii=False)}
我眼前的人、关系、所知与误知：{json.dumps(state, ensure_ascii=False)}
此刻压在我身上的事：{current_pressure}
我面对他们时可能带着的误判或顾忌：{relationship_misread}

## 我确实置身的场景
{json.dumps(scene, ensure_ascii=False)}

## 我在这场戏里依次经历的时刻
{json.dumps(moments, ensure_ascii=False)}

从自己的冲动出发经历这些时刻，但不把冲动解释给读者。只交我的话与我亲手做的事，不替别人回答。场景锚点不是要我照着演的行动表。世界事实只从本场已知资料来：不知道具体设备部件、道具、读数或往事时，不能靠职业知识补成现场证据；我的自主性在回应方式，不在创造新的物证。

返回一个 JSON 对象：{output_shape}。entries 是我整场自然发生的发言与行为，按时间顺序零至 {MAX_ACTOR_ENTRIES} 项；每项指向发生时最近的 beat_id，同一锚点可有多项，也可没有。private_impulse 写第一人称未出口念头；first_person_action 写第一人称可见动作，没有就留空；spoken 写真正说出口的台词，不带引号或批注，没有就留空。每项至少有一种外显表达。不要为了填满锚点而制造话或动作。"""


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
) -> dict[str, Any]:
    speaker = _actor_scene_speaker(beats, speaker or str(payload.get("speaker") or ""))
    if speaker not in set(brief.get("participants") or ()):
        raise ValueError("actor scene speaker is outside scene participants")
    if payload.get("scene_id") != brief.get("scene_id") or payload.get("speaker") != speaker:
        raise ValueError("actor scene target mismatch")
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_ACTOR_ENTRIES:
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
    sources: str, task: dict[str, Any] | None = None,
) -> str:
    focus = set((task or {}).get("focus_beats") or [beat["beat_id"] for beat in beats])
    selected = [beat for beat in beats if beat["beat_id"] in focus]
    return f"""# Independent Environment Writing

你是本场独立的环境描写写手。主创只给你视角与事实边界，不替你决定看哪一处、用哪种感官、句子怎样起伏。让环境在这个人的可感知范围里发生，而不是填写光、声、气味清单：某处细节可停留，也可一笔带过，不必每句都推进剧情。普通且不承担证据作用的质感可以自由试写；一旦痕迹、器物状态或声音会像线索，就须有来源。只写环境本身，不写人物动作、心理、对白或设备诊断；不增新地点、历史、天气、规则或关键事件，不解释主题。参考选段用于感受表达可能性，不复制原句、专名或特定物件。

## SceneBrief
{json.dumps({key: brief.get(key) for key in ('scene_id', 'objective', 'viewpoint', 'location', 'canon_constraints', 'participants')}, ensure_ascii=False)}

## Main Creator's Scene-Specific Perception Boundary
{json.dumps(task or {}, ensure_ascii=False)}

## Moments Available For Environmental Writing
{json.dumps(selected, ensure_ascii=False)}

## Style Reference
{style_reference[:4_000] or '沿用项目当前文风。'}

## Confirmed Sources
{sources[:8_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"{brief['scene_id']}","passages":[{{"beat_id":"所选节拍的 beat_id","focal_character":"现有视角人物或空串","description":"独立环境描写，不含人物动作和对白"}}]}}。从所选节拍中挑真正需要环境语言的位置，返回零至四段；若此场无需独立环境段，就返回空数组。长短由场景决定，每段不超过 350 字。不要附“这段象征什么”的说明，不把参考选段的原句、专名或连续措辞带入本作。"""


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
    if any(marker in values["description"] for marker in ("“", "”", "说：")):
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
