"""Preserved, bounded candidate sessions for scene description roles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    parse_describer_candidates, render_describer_initialization, render_describer_turn,
)

from .pi_scene_payload import _answer_payload


_ROLE_BY_KIND = {
    "character-description": "character-describer",
    "event-narration": "event-narrator",
    "scene-description": "scene-describer",
}


def continue_scene_describer(
    *, brief: dict[str, Any], request: dict[str, str], state: dict[str, Any],
    style_reference: str, sources: str, cache_root: Path, digest: str,
    invoke_role_turn: Callable[[str, str, tuple[tuple[str, str], ...], str], tuple[str, str]],
    cached_payload: Callable[..., dict[str, Any]],
    prompt_layers: dict[str, str] | None = None,
    request_id: str = "",
) -> list[dict[str, str]]:
    kind = request["kind"]
    role = _ROLE_BY_KIND[kind]
    layers = prompt_layers or {}
    identity_layer = {
        "character-description": "scene.describer.character",
        "event-narration": "scene.describer.event",
        "scene-description": "scene.describer.scene",
    }[kind]
    session_key = f"{kind}:{request['target']}"
    sessions = state.setdefault("describer_sessions", {})
    session = sessions.setdefault(session_key, {
        "initialization": render_describer_initialization(
            kind, style_reference, layers.get(identity_layer, ""),
        ),
        "history": [],
    })
    history = tuple((str(row[0]), str(row[1])) for row in session["history"][-12:])
    prompt = render_describer_turn(
        kind, brief, target=request["target"], purpose=request["purpose"],
        scene_moment=request["scene_moment"], cue=request["cue"],
        confirmed_sources=sources, public_stage=state.get("public_log") or [],
        literary_guidance=layers.get("scene.description.turn", ""),
    )
    key = hashlib.sha256(json.dumps([session["initialization"], history, prompt], ensure_ascii=False).encode()).hexdigest()[:12]
    path = cache_root / f"describer-{digest}-{key}.json"

    def produce() -> dict[str, Any]:
        answer, _ = invoke_role_turn(role, session["initialization"], history, prompt)
        return {"answer": answer, "payload": _answer_payload(answer)}

    def validate(record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record.get("answer"), str) or not isinstance(record.get("payload"), dict):
            raise ValueError("describer conversation record is incomplete")
        parse_describer_candidates(record["payload"], kind)
        return record

    record = cached_payload(path, produce, validate)
    candidates = parse_describer_candidates(record["payload"], kind)
    sequence = len(state.get("description_requests") or []) + 1
    result = [{
        "candidate_id": f"d{sequence}:{index}", "kind": kind, "target": request["target"],
        "purpose": request["purpose"], "scene_moment": request["scene_moment"],
        **candidate,
    } for index, candidate in enumerate(candidates, 1)]
    session["history"] = [*session["history"], [prompt, record["answer"]]][-12:]
    state.setdefault("description_requests", []).append({
        "kind": kind, "target": request["target"], "purpose": request["purpose"],
        "candidate_ids": [item["candidate_id"] for item in result],
    })
    state.setdefault("description_candidates", []).extend(result)
    if request_id:
        state.setdefault("fulfilled_requests", []).append(request_id)
    return result
