"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
import re
from typing import Any


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v2"
MAX_BEATS = 4


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
) -> str:
    """Ask the main creative model to direct actors without drafting prose."""

    return f"""# Scene Performance Direction

你是本场主创导演。剧情、人物和事件已经由 SceneBrief 与来源确定；现在只填写至多 {MAX_BEATS} 个关键节拍的表演任务单，不写正文，不新增事件。每个任务只锁定此刻已经发生什么、该人物在对话中必须争取或阻止的结果、最少量必须当场公开或暂扣的事实、不能越过的行动/对手反应边界、环境用途。speech_act 只写互动目标与压力，不指定人物采用哪种话术、论证顺序、职业术语、情绪表演或身体姿态；这些由扮演该人物的演员自行选择。information 不是整场解释清单，只列当前回合必须说出的已确认事实；其他已知信息留给主创在整场安排。不摘录人物卡示例句或口头禅。不得临场发明钟点、设备读数、节目时间表、歌名、计数等精确信息；若来源只说“大致顺序”，任务单也只允许大致顺序。动作边界不得授权来源未给的道具、旧物或往事。不能用“展示性格”“推进剧情”这类空任务。没有对白的节拍 speaker 留空。

## SceneBrief
{json.dumps(brief, ensure_ascii=False)}

## Expression And Voice
{json.dumps(expression, ensure_ascii=False)}

## Confirmed Sources
{sources[:10_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"与 SceneBrief 相同","beats":[{{"beat_id":"b1","event":"已确定的具体行动","speaker":"participants 中的精确字符串或空串","speech_act":"必须完成的具体言语行为","information":"须说出/隐瞒的信息","action_boundary":"允许的身体行动及不可改变的结果","response_boundary":"对手反应边界","environment_need":"视角与空间用途"}}]}}。
不得改变 Canon、人物名单、时间数值、场景结局；不得预写标准台词或环境段落。"""


def parse_performance_plan(payload: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if str(payload.get("scene_id") or "") != str(brief.get("scene_id") or ""):
        raise ValueError("performance plan scene_id mismatch")
    beats = payload.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("performance plan requires 1-4 beats")
    participants = set(brief.get("participants") or ())
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(beats, 1):
        normalized.append(_parse_beat(item, index, participants))
    return {"schema": PERFORMANCE_SCHEMA, "scene_id": brief["scene_id"], "beats": normalized}


def _parse_beat(item: Any, index: int, participants: set[str]) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("beat_id") != f"b{index}":
        raise ValueError("performance beat_id must be sequential")
    fields = ("event", "speaker", "speech_act", "information", "action_boundary", "response_boundary", "environment_need")
    beat = {key: str(item.get(key) or "").strip() for key in fields}
    if not beat["event"] or len(beat["event"]) > 300:
        raise ValueError("performance beat requires a bounded event")
    if beat["speaker"] and beat["speaker"] not in participants:
        raise ValueError("performance speaker is outside scene participants")
    if beat["speaker"] and not beat["speech_act"]:
        raise ValueError("speaking beat requires a speech act")
    if any(len(value) > 220 for value in beat.values()):
        raise ValueError("performance beat field is too long")
    return {"beat_id": f"b{index}", **beat}


def render_actor_prompt(
    brief: dict[str, Any], beat: dict[str, str], voice: dict[str, Any],
) -> str:
    person = _actor_identity(voice, beat["speaker"])
    state = voice.get("voice_state") if isinstance(voice.get("voice_state"), dict) else {}
    scene = {key: brief.get(key) for key in ("scene_id", "participants", "location")}
    action_boundary = beat["action_boundary"] or "不得自造新事件或关键物件。"
    response_boundary = beat["response_boundary"] or "停在对方能回应的地方。"
    return f"""# 我在场：{person['name']}

从现在起，我就是这个人，不是描写此人的助手、导演或评论者。我只知道下列身份与眼前情境；在不改变已发生事件的前提下，我自己决定怎样回应。我在心里以第一人称经历它，然后交出我此刻真正会说的话，以及我亲手做的动作。JSON 只是交付容器，不改变我的内在视角。

## 我是谁，我带着什么进入此刻
我的身份：{person['role']}
我相信：{person['belief']}
我想要：{person['wants']}
我避开或害怕：{person['avoids']}
我的底线：{person['moral_line']}
过往在我身上留下的行为痕迹：{json.dumps(person['background_influence'], ensure_ascii=False)}
我的稳定说话方式：{json.dumps(person['stable_voice'], ensure_ascii=False)}
我眼前的人、关系、所知与误知：{json.dumps(state, ensure_ascii=False)}

## 我现在确实置身的场景
{json.dumps(scene, ensure_ascii=False)}

## 我眼前正发生的事
{beat['event']}

## 我不能改变的动作结果
{action_boundary}

## 他人的回应不由我代写
{response_boundary}

我先抓住自己最不愿让眼前这个人察觉的冲动，再决定身体先做什么，最后才开口。我不知道导演的台词计划，也不需要替整场解释事实；此刻怎样争取、回避、还口或沉默，由我自己决定。台词朝眼前的人做事，只演出一个对话回合；private_impulse 中的压力须在 spoken 的避词、称呼、句子走向或停顿里留下痕迹，不能把个性全藏进内心栏，让说出口的仍是中性公告。我用自己的词域和句法节奏，不照念人物卡范例。动作从我的身体与目标生出，只用眼前已确认的物件，不增添新道具、储物设施或设备细节。

仅返回一个 JSON 候选，candidates 数组长度必须恰好为 1，不要备选。按内在冲动 → 身体动作 → 出口台词的顺序填写：{{"beat_id":"{beat['beat_id']}","speaker":"{beat['speaker']}","candidates":[{{"private_impulse":"我没说出口的短促念头或欲望；用第一人称，不分析关系效果","first_person_action":"我当下亲手做的可见动作；用第一人称，不写‘他/她’式旁白","spoken":"我真正说出口的台词，不带说话者名、引号或导演批注"}}]}}。
不能替别人回答，也不能改变已给的事件或动作结果。精确钟点、数量、设备读数、歌名和往事只有我在上面确实知道才能说；没有就用角色自然的非精确说法。不要新增身份、物件、情节转折或完整场景。"""


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
        if not values["spoken"] or len(values["spoken"]) > 300 or not values["first_person_action"] or len(values["first_person_action"]) > 220:
            raise ValueError("actor candidate dialogue/action is missing or too long")
        if len(values["private_impulse"]) > 160:
            raise ValueError("actor candidate private impulse is too long")
        normalized.append(values)
    return {"schema": PERFORMANCE_SCHEMA, "beat_id": beat["beat_id"], "speaker": beat["speaker"], "candidates": normalized}


def render_environment_prompt(
    brief: dict[str, Any], beats: list[dict[str, str]], style_reference: str,
    sources: str,
) -> str:
    return f"""# Independent Environment Writing

你是本场独立的环境描写写手。按已确定节拍写可供主创选择的小说环境描写，不是物件清单。空间、光、声、触感和时间流动须由本场视角与人物行动触发；可让读者停留并感受语言起伏，不强迫每句承担情节推进。只写环境本身及其可感知变化，不写人物动作、心理、对白、设备诊断或新发现；这些由主创和角色 Agent 负责。不得凭空开辟新地点、历史、天气、规则、关键物件或事件；不得解释主题或宣布情绪。

## SceneBrief
{json.dumps({key: brief.get(key) for key in ('scene_id', 'objective', 'viewpoint', 'location', 'canon_constraints', 'participants')}, ensure_ascii=False)}

## Locked Beats
{json.dumps(beats, ensure_ascii=False)}

## Style Reference
{style_reference[:4_000] or '沿用项目当前文风。'}

## Confirmed Sources
{sources[:8_000] or '无额外来源。'}

仅返回 JSON：{{"scene_id":"{brief['scene_id']}","passages":[{{"beat_id":"b1","focal_character":"现有视角人物或空串","description":"150—300 字的独立环境描写，不含人物动作和对白","scene_function":"为何此刻被感知"}}]}}。至多四段，每段不超过 350 字；不把参考选段的原句、专名或连续措辞带入本作。"""


def parse_environment_material(payload: dict[str, Any], brief: dict[str, Any], beats: list[dict[str, str]]) -> dict[str, Any]:
    if payload.get("scene_id") != brief.get("scene_id"):
        raise ValueError("environment material scene_id mismatch")
    passages = payload.get("passages")
    if not isinstance(passages, list) or not 1 <= len(passages) <= MAX_BEATS:
        raise ValueError("environment material requires one to four passages")
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
        "以下是各独立 Agent 的非权威候选素材。你是唯一正文作者：逐项判断是否合乎剧情、人物与文风；可以全部拒绝、重写或重新安排，不可机械拼贴。演员只看到眼前情境和动作边界；完整 plan 的 speech_act 与 information 仍由你在整场正文兑现，演员没说出的剧情义务并未取消。角色的 first_person_action 是演员的第一人称动作自述，不是正式叙述视角；须按本场叙述视角重写。private_impulse 与 scene_function 是后台提示，绝不可写入正文。环境候选只提供空间与感知，不得由它决定人物动作、台词或事实。候选中的新增事实不获得 Canon 权限，尤其不能从候选带入来源未确认的钟点、读数、数量、歌名或新物件；候选自身不能作为这些事实的证据。",
        json.dumps({"plan": plan, "actor_candidates": actors, "environment_candidates": environment or {}}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 16_000:
        raise ValueError("scene performance material block exceeds prompt budget")
    return block


__all__ = [
    "PERFORMANCE_SCHEMA", "render_performance_plan_prompt", "parse_performance_plan",
    "render_actor_prompt", "parse_actor_material", "render_environment_prompt",
    "parse_environment_material", "render_performance_materials",
]
