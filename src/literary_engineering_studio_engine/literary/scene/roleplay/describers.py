"""Tool-free description candidates directed by the sole scene author."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.prompting.layers import prompt_layer_spec, render_prompt_template


DESCRIBER_KINDS = frozenset({"character-description", "object-description", "scene-description"})

_KIND_LAYER = {
    "character-description": "scene.describer.character",
    "object-description": "scene.describer.object",
    "scene-description": "scene.describer.scene",
}


def render_describer_initialization(kind: str, style: str, literary_guidance: str = "") -> str:
    if kind not in DESCRIBER_KINDS:
        raise ValueError("unknown describer kind")
    identity = _KIND_LAYER[kind]
    return render_prompt_template("scene.describer.initialization.protocol", (
        kind,
        (literary_guidance or prompt_layer_spec(identity).default_text) + "\n"
        + prompt_layer_spec(identity + ".protocol").default_text,
        style[:2000] or '依已确认的作品资料，避免套用固定文风。',
    ))


def render_describer_turn(
    kind: str, brief: dict[str, Any], *, target: str, purpose: str, scene_moment: str,
    cue: str, confirmed_sources: str, public_stage: list[dict[str, str]],
    literary_guidance: str = "",
) -> str:
    if kind not in DESCRIBER_KINDS:
        raise ValueError("unknown describer kind")
    context = {
        "scene_id": brief.get("scene_id"), "viewpoint": brief.get("viewpoint"),
        "location": brief.get("location"), "participants": brief.get("participants"),
        "target": target, "literary_purpose": purpose, "scene_moment": scene_moment,
        "cue": cue, "confirmed_sources": confirmed_sources[:5_000],
        "public_stage": public_stage[-16:],
    }
    return render_prompt_template("scene.describer.turn.protocol", (
        json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        literary_guidance or prompt_layer_spec("scene.description.turn").default_text,
    ))


def parse_describer_candidates(payload: dict[str, Any], kind: str) -> list[dict[str, str]]:
    if kind not in DESCRIBER_KINDS or not isinstance(payload, dict):
        raise ValueError("invalid describer response")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ValueError("describer must return zero to three candidates")
    result = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("describer candidate must be an object")
        text = str(item.get("text") or "").strip()
        focus = str(item.get("focus") or "").strip()
        if not 5 <= len(text) <= 700 or not focus or len(focus) > 160:
            raise ValueError("describer candidate needs bounded text and focus")
        result.append({"text": text, "focus": focus})
    if not result and not str(payload.get("no_material_reason") or "").strip():
        raise ValueError("empty describer response needs a reason")
    return result
