"""Bounded, non-authoritative scene performance material contracts."""

from __future__ import annotations

import json
from typing import Any


PERFORMANCE_SCHEMA = "arcvellum/scene-performance/v1"
MAX_BEATS = 4


def render_performance_plan_prompt(
    brief: dict[str, Any], expression: dict[str, Any], sources: str,
) -> str:
    """Ask the main creative model to direct actors without drafting prose."""

    return f"""# Scene Performance Direction

你是本场主创导演。剧情、人物和事件已经由 SceneBrief 与来源确定；现在只填写至多 {MAX_BEATS} 个关键节拍的表演任务单，不写正文，不新增事件。每个任务说清此刻实际发生什么、该人物必须完成什么言语行为、须传递或暂扣什么信息、允许哪些动作、对手反应边界、环境描写应服务什么。speech_act 只写语言行为与对手压力，不摘录人物卡里的示例句、口头禅或“不是……而是……”式标准说法；具体措辞留给演员。information 只能锁定来源已确认且当前节拍必须说出的事实，不替角色临场发明“每天几点到店”、设备读数、节目时间表、歌名、计数等精确信息；若来源只说“大致顺序”，任务单也只允许大致顺序。动作边界也不得授权来源未给的道具、旧物或往事。不能用“展示性格”“推进剧情”这类空任务。没有对白的节拍 speaker 留空。

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
    prior_lines: list[str], sources: str,
) -> str:
    return f"""# Character Performance

你现在扮演且只扮演 `{beat['speaker']}`。从这个人的已知事实、误判、欲望、羞耻、关系与语言习惯出发，真实地说话并行动；不要替其他人物说话，不要站到全知作者的位置解释心理。当前剧情动作和必须完成的言语行为已经决定，你只创造个人化的具体说法、回避、节奏与伴随动作。行动可以笨拙、幽默、失礼或迟疑，不能统一为中性短句或重复摸杯、抬下颌一类安全动作。人物卡里的示例台词只说明说话机制，不是可复用的原句或口头禅；同一场的不同节拍尤其不能反复用相同开头、同一种纠正措辞或同一套程序解释。让这一次回答受眼前对手和具体压力改变，少量关键细节比复述整张清单更有力。

## Scene Constraints
{json.dumps({key: brief.get(key) for key in ('scene_id', 'participants', 'canon_constraints', 'objective', 'viewpoint', 'location')}, ensure_ascii=False)}

## Current Beat Task
{json.dumps(beat, ensure_ascii=False)}

## Character Voice And Knowledge
{json.dumps(voice, ensure_ascii=False)}

## Prior Candidate Lines (not yet final prose)
{json.dumps(prior_lines[-3:], ensure_ascii=False)}

## Confirmed Sources
{sources[:6_000] or '无额外来源。'}

仅返回 JSON：{{"beat_id":"{beat['beat_id']}","speaker":"{beat['speaker']}","candidates":[{{"spoken":"这个人会实际说出的台词，不带引号或说话者名","visible_action":"与台词共生的具体可见动作","subtext_effect":"这句话试图对关系造成什么作用"}}]}}。给一至两种有真实差异的候选。若任务单只要求寒暄、回避或大致顺序，就只说到这个粒度；不要用自造的钟点、日期、持续时长、数量、设备读数、歌名或节目表填满台词。需要精确事实而任务单未给出时，用不含精确值的自然说法，留给主创核对。别把“不是……而是……”和自我解释当作对话默认收束。不得增加身份、往事、情节转折或他人回应；不得写完整场景。"""


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
        values = {key: str(item.get(key) or "").strip() for key in ("spoken", "visible_action", "subtext_effect")}
        if not values["spoken"] or len(values["spoken"]) > 300 or len(values["visible_action"]) > 220:
            raise ValueError("actor candidate dialogue/action is missing or too long")
        if len(values["subtext_effect"]) > 160:
            raise ValueError("actor candidate subtext is too long")
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
        "以下是各独立 Agent 的非权威候选素材。你是唯一正文作者：逐项判断是否合乎剧情、人物与文风；可以全部拒绝、重写或重新安排，不可机械拼贴。环境候选只提供空间与感知，不得由它决定人物动作、台词或事实；subtext_effect 和 scene_function 是后台提示，绝不可写入正文。候选中的新增事实不获得 Canon 权限，尤其不能从候选带入来源未确认的钟点、读数、数量、歌名或新物件；候选自身不能作为这些事实的证据。",
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
