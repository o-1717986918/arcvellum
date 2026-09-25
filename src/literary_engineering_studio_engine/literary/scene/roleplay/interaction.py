"""Pure prompts and candidate handoff for director-led scene interaction."""

from __future__ import annotations

import json
from typing import Any

from .relay_context import validated_public_log


def parse_scene_material_requests(
    payload: dict[str, Any], brief: dict[str, Any], plan: dict[str, Any],
    *, actor_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Read the main creator's optional request without treating it as prose."""

    raw = payload.get("material_requests", [])
    if not isinstance(raw, list):
        raise ValueError("material_requests must be a list")
    participants = set(brief.get("participants") or ())
    beat_ids = {beat["beat_id"] for beat in plan["beats"]}
    entry_beats = {str(entry.get("entry_id") or ""): str(entry.get("beat_id") or "")
                   for entry in actor_entries or [] if isinstance(entry, dict)}
    return [_parse_material_request(item, participants, beat_ids, plan["beats"][0]["beat_id"], entry_beats)
            for item in raw]


def _parse_material_request(
    item: Any, participants: set[str], beat_ids: set[str], default_beat: str,
    entry_beats: dict[str, str],
) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("kind") not in {"actor", "environment"}:
        raise ValueError("material request kind must be actor or environment")
    kind = item["kind"]
    speaker = str(item.get("speaker") or "").strip()
    beat_id = str(item.get("beat_id") or default_beat).strip()
    beat_id = entry_beats.get(beat_id, beat_id)
    cue = str(item.get("cue") or "").strip()
    scene_change = str(item.get("scene_change") or "").strip()
    if beat_id not in beat_ids or not cue or len(cue) > 800 or len(scene_change) > 800:
        raise ValueError("material request needs a known beat and a concise scene cue")
    if not _valid_material_role(kind, speaker, scene_change, participants):
        raise ValueError("material request speaker is outside its role")
    return {"kind": kind, "speaker": speaker, "beat_id": beat_id, "scene_change": scene_change, "cue": cue}


def _valid_material_role(kind: str, speaker: str, scene_change: str, participants: set[str]) -> bool:
    return speaker in participants if kind == "actor" else not (speaker or scene_change)


def render_interaction_direction_prompt(
    brief: dict[str, Any], plan: dict[str, Any], public_log: list[dict[str, Any]],
    turn: int, sources: str,
) -> str:
    """Let the main creator choose the next participant and situation, not their line."""

    observed = validated_public_log(brief, public_log[-24:])
    unheard = [name for name in brief.get("participants") or ()
               if name not in {entry.get("speaker") for entry in public_log}]
    direction_plan = {key: plan[key] for key in ("beats", "actor_tasks", "opening_direction", "unknown_slots")
                      if key in plan}
    return f"""# Scene Interaction Direction

你是本场主创，负责场景的情节、关系、设定与世界状态方向。根据已经真正发生的公开言行，决定下一轮谁最有理由回应，以及关系、认知或选择怎样推进。先辨认此人主要在对谁说话、回应对方哪一句话或哪件事；若是主动开口，给出他此刻可见、可闻或已知的起因。误称、误会和追问也要有具体的对象与来由，使人物间的关系成为话题。计划中尚未由演员说出的话、做出的事仍是可能性；让发起者先表演，下一位才能接住其具体内容。cue 用一到三句话写此人可感的事实、对话对象与关系压力。情节确需某人说出关键称呼、透露事实或完成特定动作时，直接向这个角色说明这次必须发生的情节事实，措辞、微动作与回应方式交给演员。scene_change 承载环境、物件及已演言行引起的外部后果；需要某位参与者说出一句关键话或做出关键动作时，先把轮次交给此人。背景配角的活动可由你在最终正文里斟酌补写。公开舞台里的言行以实际记录为准。往事、秘密与世界规则可以等人物自己找到说出口的理由。director_note 留给正文组织时使用，记下本轮发现的关系变化或尚待兑现的可能。同一人可以连续回应，也可以沉默或结束。单人戏可与空间、事件、消息、器物阻力及自己的决定互动。场景目标尚未抵达时，允许表演继续探索。

本场大局与设定来源：{json.dumps(brief, ensure_ascii=False)}
既有导演计划：{json.dumps(direction_plan, ensure_ascii=False)}
已确认来源：{sources[:7_000] or '仅 SceneBrief。'}
第 {turn + 1} 轮之前的公开舞台：{json.dumps(observed, ensure_ascii=False)}
仍未获得自身表演回合的本场人物：{json.dumps(unheard, ensure_ascii=False)}。若他们将在本场说话或做出影响关系的动作，给他们一次自己的回应机会；也可在已确认情势变化后轮到他们。

仅返回 JSON：{{"finish":false,"next_speaker":"SceneBrief.participants 中的人物；结束时为空","beat_id":"计划中的节拍 ID；结束时为空","scene_change":"本轮新进入的外部变化，可以为空","cue":"此人主要面对谁、凭哪件已发生的事开口，以及此刻的关系压力；可交代必须说出的关键称呼或情节事实","director_note":"主创留给最终正文的情节、设定或世界变化判断，不当作已经证实的事实"}}。若表演已有足够素材，finish=true，其余字段可为空。"""


def parse_interaction_direction(payload: dict[str, Any], brief: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("finish"), bool):
        raise ValueError("interaction direction requires a finish decision")
    finish = payload["finish"]
    speaker = str(payload.get("next_speaker") or "").strip()
    beat_id = str(payload.get("beat_id") or "").strip()
    _validate_direction_target(finish, speaker, beat_id, brief, plan)
    values = {key: str(payload.get(key) or "").strip() for key in ("scene_change", "cue", "director_note")}
    if max(map(len, values.values())) > 400:
        raise ValueError("interaction direction is too long")
    return {"finish": finish, "next_speaker": "" if finish else speaker,
            "beat_id": "" if finish else beat_id, **values}


def _validate_direction_target(
    finish: bool, speaker: str, beat_id: str, brief: dict[str, Any], plan: dict[str, Any],
) -> None:
    if finish:
        return
    if speaker not in set(brief.get("participants") or ()) or beat_id not in {beat["beat_id"] for beat in plan["beats"]}:
        raise ValueError("interaction direction must choose a scene participant and known beat")


def render_actor_interaction_prompt(
    brief: dict[str, Any], plan: dict[str, Any], direction: dict[str, Any],
    public_log: list[dict[str, Any]], environment_cue: str, character_context: str = "",
) -> str:
    speaker = direction["next_speaker"]
    observed = validated_public_log(brief, public_log[-24:])
    return f"""# 当前这一轮

{f'我对自己、别人和这世界的已知经历与看法：{character_context}' if character_context else ''}
此刻发生了什么：{direction['scene_change'] or next(beat['event'] for beat in plan['beats'] if beat['beat_id'] == direction['beat_id'])}
当前面对的局面：{direction['cue'] or '依据自己的处境回应。'}
周围可感的空间素材：{environment_cue or '自行感受已有场景。'}
此前实际发生的公开言行：{json.dumps(observed, ensure_ascii=False)}

我只扮演自己。可以说话、行动、两者兼有或暂时不回应；我留意这次主要面对谁、对方实际说过或做过什么，再按自己的兴致、误解、关系和当下情绪回应。若我先挑起话头，所见所闻和我自己的念头会成为起因。我知道的往事、盼望、恐惧与矛盾可以进入我的想法和说话方式；面对他人时，我有权试探、改口、追问、拒绝、坦白或转移话题，也有权把重要的事留到以后。若当前局面明确交给我一个必须发生的关键称呼或情节事实，我以自己的口气把它完成，其他言行仍由我选择。请把这一轮当作一次真实回应，写一个 JSON 条目；spoken 可以有连续的、多句的、会转弯的话，行动与私念也可随这一次回应展开。下一位角色会根据我真正说出和做出的内容接话。仅返回 JSON：{{"scene_id":"{brief['scene_id']}","speaker":"{speaker}","entries":[{{"beat_id":"{direction['beat_id']}","spoken":"我这一轮说的话，可为空","first_person_action":"我这一轮做的可见动作，可为空","private_impulse":"我没说出的当下想法，可为空"}}]}}。若选择沉默且没有动作，entries 返回空数组。

"""


def render_interaction_materials(
    plan: dict[str, Any], directions: list[dict[str, Any]], actor_entries: list[dict[str, Any]],
    environment: dict[str, Any] | None, *, viewpoint: str = "",
) -> str:
    """Give the sole prose author a chronological, selectable rehearsal record."""

    visible = [{**entry, "private_impulse": ""} if viewpoint and entry.get("speaker") != viewpoint else entry
               for entry in actor_entries]
    turns = []
    previous_change = ""
    for direction in directions:
        turn = {key: direction[key] for key in ("turn", "next_speaker", "beat_id", "entry_ids")
                if key in direction}
        change = str(direction.get("scene_change") or "").strip()
        if change and change != previous_change:
            turn["scene_change"] = change
        if change:
            previous_change = change
        turns.append(turn)
    block = "\n".join((
        "以下是逐轮对演的候选资料。actor_entries 按发生顺序排列，entry_id 可用于取舍和修订；director_turns 中的 scene_change 是该轮新进入的外部情势候选，供你还原人物回应的起因。你是唯一正文作者：挑出真正改变关系的回合，其余可省略、转述或融入时间流；台词可改写，必要的衔接言行也可由你补写。人物话语可先于动作出现，也可被心理、环境或沉默接走，让叙述段落形成自己的呼吸。避免逐条把 spoken 与 first_person_action 排成引号加说话动作的清单。设定展开、宏观情节、世界状态变化、视角心理、环境融合、结构节奏和文学表达仍由你完成。需要听见角色新的自主选择时可请求续演。未决情节与世界事实依据 SceneBrief 和已确认来源判断并如实申报。环境候选供你自由取景。",
        json.dumps({"beats": plan["beats"], "director_turns": turns, "actor_entries": visible,
                    "environment_candidates": environment or {}}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 20_000:
        raise ValueError("interaction material block exceeds prompt budget")
    return block


__all__ = ["parse_interaction_direction", "parse_scene_material_requests", "render_actor_interaction_prompt", "render_interaction_direction_prompt", "render_interaction_materials"]
