"""Pure prompts and candidate handoff for director-led scene interaction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from literary_engineering_studio_engine.prompting.layers import prompt_layer_spec, render_prompt_template

from .relay_context import validated_public_log


MATERIAL_KINDS = frozenset({
    "actor", "environment", "character-description", "event-narration", "scene-description",
})


@dataclass(frozen=True)
class MaterialRequestV2:
    kind: str
    target: str
    purpose: str
    scene_moment: str
    cue: str
    beat_id: str = ""
    scene_change: str = ""

    def to_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


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
    if not isinstance(item, dict) or item.get("kind") not in MATERIAL_KINDS:
        raise ValueError("material request kind is unsupported")
    kind = item["kind"]
    speaker = str(item.get("target") or item.get("speaker") or "").strip()
    beat_id = str(item.get("beat_id") or default_beat).strip()
    beat_id = entry_beats.get(beat_id, beat_id)
    cue = str(item.get("cue") or "").strip()
    scene_change = str(item.get("scene_change") or "").strip()
    purpose = str(item.get("purpose") or "").strip()
    scene_moment = str(item.get("scene_moment") or "").strip()
    _check_material_request(item, kind, speaker, beat_id, cue, scene_change,
                            purpose, scene_moment, beat_ids, participants)
    return {"kind": kind, "speaker": speaker, "target": speaker, "beat_id": beat_id,
            "scene_change": scene_change, "cue": cue, "purpose": purpose, "scene_moment": scene_moment}


def _check_material_request(
    item: dict[str, Any], kind: str, speaker: str, beat_id: str, cue: str,
    scene_change: str, purpose: str, scene_moment: str,
    beat_ids: set[str], participants: set[str],
) -> None:
    if beat_id not in beat_ids or not cue or len(cue) > 800 or len(scene_change) > 800:
        raise ValueError("material request needs a known beat and a concise scene cue")
    if len(purpose) > 300 or len(scene_moment) > 200 or len(speaker) > 120:
        raise ValueError("material request literary purpose, moment, or target is too long")
    if "target" in item and (not purpose or not scene_moment):
        raise ValueError("material request needs a literary purpose and scene moment")
    if not _valid_material_role(kind, speaker, scene_change, participants):
        raise ValueError("material request speaker is outside its role")


def _valid_material_role(kind: str, speaker: str, scene_change: str, participants: set[str]) -> bool:
    if kind in {"actor", "character-description"}:
        return speaker in participants
    if kind == "event-narration":
        return bool(speaker) and not scene_change
    return not scene_change and (kind != "environment" or not speaker)


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
    literary_guidance: str = "",
) -> str:
    speaker = direction["next_speaker"]
    observed = validated_public_log(brief, public_log[-24:])
    return render_prompt_template("scene.actor.interaction.protocol", (
        f'我对自己、别人和这世界的已知经历与看法：{character_context}' if character_context else '',
        direction['scene_change'] or next((beat['event'] for beat in plan['beats'] if beat['beat_id'] == direction['beat_id'])),
        direction['cue'] or '依据自己的处境回应。',
        environment_cue or '自行感受已有场景。',
        json.dumps(observed, ensure_ascii=False),
        brief['scene_id'],
        speaker,
        direction['beat_id'],
        literary_guidance or prompt_layer_spec("scene.actor.turn").default_text,
    ))


def render_interaction_materials(
    plan: dict[str, Any], directions: list[dict[str, Any]], actor_entries: list[dict[str, Any]],
    environment: dict[str, Any] | None, *, viewpoint: str = "",
    description_candidates: list[dict[str, str]] | None = None,
    material_notices: list[dict[str, str]] | None = None,
    literary_guidance: str = "",
) -> str:
    """Give the sole prose author a chronological, selectable rehearsal record."""

    visible = [{**entry, "private_impulse": ""} if viewpoint and entry.get("speaker") != viewpoint else entry
               for entry in actor_entries]
    turns = _visible_director_turns(directions)
    block = "\n".join((
        literary_guidance or prompt_layer_spec("scene.material.selection").default_text,
        json.dumps({"beats": plan["beats"], "director_turns": turns, "actor_entries": visible,
                    "environment_candidates": environment or {},
                    "description_candidates": description_candidates or [],
                    "material_notices": material_notices or []}, ensure_ascii=False, separators=(",", ":")),
    ))
    if len(block) > 20_000:
        raise ValueError("interaction material block exceeds prompt budget")
    return block


def _visible_director_turns(directions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns = []
    previous_change = ""
    previous_notes: set[str] = set()
    for direction in directions:
        turn = {key: direction[key] for key in ("turn", "next_speaker", "beat_id", "entry_ids")
                if key in direction}
        change = str(direction.get("scene_change") or "").strip()
        if change and change != previous_change:
            turn["scene_change"] = change
        if change:
            previous_change = change
        for key in ("cue", "director_note"):
            value = str(direction.get(key) or "").strip()
            if value and not _repeated_phrase(value):
                value = value[:260]
                if key != "director_note" or value not in previous_notes:
                    turn[key] = value
                    if key == "director_note":
                        previous_notes.add(value)
        turns.append(turn)
    return turns


def _repeated_phrase(value: str) -> bool:
    if len(value) < 80:
        return False
    return any(len(value) % size == 0 and value == value[:size] * (len(value) // size)
               for size in range(2, min(80, len(value) // 4) + 1))


__all__ = ["MaterialRequestV2", "parse_interaction_direction", "parse_scene_material_requests", "render_actor_interaction_prompt", "render_interaction_materials"]
