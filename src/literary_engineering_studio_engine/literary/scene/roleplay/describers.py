"""Tool-free description candidates directed by the sole scene author."""

from __future__ import annotations

import json
import re
from typing import Any

from literary_engineering_studio_engine.prompting.layers import prompt_layer_spec, render_prompt_template


DESCRIBER_KINDS = frozenset({"character-description", "event-narration", "scene-description"})

_KIND_LAYER = {
    "character-description": "scene.describer.character",
    "event-narration": "scene.describer.event",
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
        "objective": brief.get("objective"), "scene_function": brief.get("scene_function"),
        "canon_constraints": brief.get("canon_constraints", []),
        "target": target, "literary_purpose": purpose, "scene_moment": scene_moment,
        "cue": cue, "confirmed_sources": confirmed_sources,
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
        result.append(_parse_describer_candidate(item, kind))
    if not result and not str(payload.get("no_material_reason") or "").strip():
        raise ValueError("empty describer response needs a reason")
    return result


def _parse_describer_candidate(item: Any, kind: str) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("describer candidate must be an object")
    text = str(item.get("text") or "").strip()
    focus = str(item.get("focus") or "").strip()
    if not 5 <= len(text) <= 12_000 or not focus or len(focus) > 160:
        raise ValueError("describer candidate needs bounded text and focus")
    candidate = {"text": text, "focus": focus}
    if kind == "event-narration":
        candidate.update(_event_basis(item))
    return candidate


def _event_basis(item: dict[str, Any]) -> dict[str, str]:
    original = str(item.get("basis") or "").strip()
    basis = _declared_event_basis(original) if original else "proposed"
    source_note = str(item.get("source_note") or "").strip()
    if basis not in {"confirmed", "attributed", "proposed"}:
        raise ValueError("event narration needs confirmed, attributed, or proposed basis and source note")
    if not original:
        source_note = "原始交付未标来源状态；整体保留为待确认创作提案。\n" + source_note
    if not source_note:
        basis = "proposed"
        source_note = "原始交付未附来源说明；整体保留为待确认创作提案。"
    if original and basis != original:
        source_note = f"来源状态原文：{original}\n{source_note}"
    if len(source_note) > 4_000:
        raise ValueError("event narration source note exceeds context capacity")
    return {"basis": basis, "source_note": source_note}


def _declared_event_basis(value: str) -> str:
    status = r"(?:confirmed|attributed|proposed)"
    annotated = status + r"(?:\s*[（(][^()（）]*[）)])?"
    if not re.fullmatch(annotated + r"(?:\s*[+＋/、,，;；|]\s*" + annotated + r")*", value):
        return ""
    declarations = re.findall(r"(?<![A-Za-z])(?:confirmed|attributed|proposed)(?![A-Za-z])", value)
    return next(label for label in ("proposed", "attributed", "confirmed") if label in declarations)
