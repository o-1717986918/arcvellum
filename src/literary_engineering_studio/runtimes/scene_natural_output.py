"""Natural answers are archived before a separate, tool-free transport extraction."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .pi_scene_payload import _answer_payload
from .commission_source_format import restore_commission_source
from .creator_delivery_labels import resolve_creator_targets
from .event_material_provenance import event_fields, recover_event_source_status
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS

NATURAL_RESPONSE_MODE = "natural-v1"
STYLE_TOKEN = "{{STYLE_DIRECTION}}"
_CREATOR_CONTRACT = {
    "material_plan": {"required_kinds": ["one or more of the five kind IDs"], "reason": "creator reason"},
    "material_requests": [{"kind": "actor/environment/character-description/event-narration/scene-description",
        "target": "actor/character-description: exact participant name from context.briefing.scene_brief.participants; other kinds: commission subject",
        "purpose": "purpose", "scene_moment": "moment", "cue": "stimulus",
        "author_prompt": "verbatim contiguous creator invitation from source_text",
        "style_direction": "verbatim contiguous style from source_text, or empty when unstated",
        "archive_attachments": [{"path": "relative archive path", "start_line": None,
                                "end_line": None, "knowledge": "known/reference for actor; empty otherwise"}],
        "character_card": "actor only: schema arcvellum/actor-character-card/v1, target, sections mapping from the supplied sixteen template keys, source_refs list, notes"}],
    "prose": "exact contiguous source text of completed body, or empty during preparation",
    "decision_summary": "creator's working intention and decisions",
    "creative_intent": {"reader_experience": "intended experience", "reader_knows": "intended understanding",
                        "reader_misreads": "intended ambiguity", "withheld": "later revelation"},
    "scene_delta": {"character_changes": [], "canon_candidates": [], "continuity_changes": [],
        "promise_updates": [], "reader_question_updates": [], "next_handoff": [], "new_asset_candidates": []},
    "material_decisions": [{"candidate_id": "existing ID", "decision": "use/adapt/discard", "reason": "creator's reason"}],
}
_MATERIAL_CONTRACT = {
    "candidates": [{"text": "exact contiguous literary source text", "focus": "literary focus",
        "spoken": "exact source speech for actor", "first_person_action": "exact actor action",
        "private_impulse": "exact private impulse if present",
        "basis": "event only: confirmed/attributed/proposed",
        "source_note": "event only: source or author's proposal note"}],
    "no_material_reason": "reason if creator offers no material",
}
_REVIEW_CONTRACT = {"decision": "pass/revise/escalate", "summary": "editor's judgment",
                    "revision_instructions": [], "evidence": []}
CONTRACTS = {"creator": _CREATOR_CONTRACT, "material": _MATERIAL_CONTRACT, "review": _REVIEW_CONTRACT}
CONTRACTS["tone"] = {"edits": [{"rule_id": "1 through 11", "before": "exact original fragment",
    "after": "verbatim proposed replacement", "reason": "editor's stated literary reason"}],
    "summary": "editor's summary; empty edits when text is retained"}
CONTRACTS["card"] = {"card": {"schema": "arcvellum/actor-character-card/v1", "target": "target from context",
    "sections": {key: "verbatim card section" for key in ACTOR_CARD_SECTIONS}, "source_refs": [], "notes": ""}}
_CHANGE = {"target_ref": "existing archive reference", "summary": "stated change",
           "evidence": "verbatim source passage", "operation": "update/create", "attributes": {}}
for _key in _CREATOR_CONTRACT["scene_delta"]:
    if _key != "next_handoff":
        _CREATOR_CONTRACT["scene_delta"][_key] = [_CHANGE]


def render_style(template: str, direction: str) -> str:
    if template.count(STYLE_TOKEN) != 1:
        raise ValueError("creative identity needs exactly one style field")
    return template.replace(STYLE_TOKEN, direction.strip() or "由本次作品与委托的语感展开。")


def creator_style(briefing: Mapping[str, Any]) -> str:
    style = briefing.get("style") or {}
    measured = style.get("stylometry") or {}
    keys = ("author_directive",) if measured.get("combine") == "replace" else ("author_directive", "mounted")
    return "\n\n".join(str(item.get("content") or "").strip()
                        for key in (*keys, "stylometry")
                        if isinstance((item := style.get(key)), dict) and item.get("content"))


class NaturalOutputProcessor:
    def __init__(self, root: Path, system_prompt: str, invoke: Callable[[str, str], str]):
        self.root, self.system_prompt, self.invoke = root, system_prompt, invoke

    def process(self, answer: str, *, kind: str, context: Mapping[str, Any]) -> dict[str, Any]:
        if not answer.strip() or len(answer) > 160_000:
            raise ValueError("natural response is empty or exceeds the transport budget")
        digest = sha256(answer.encode("utf-8")).hexdigest()
        directory = self.root / "natural-answers" / digest
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "original.md").write_text(answer, encoding="utf-8")
        context = {key: value for key, value in context.items() if key != "delivery_feedback"}
        fingerprint = sha256(json.dumps(["verbatim-commission-v2", kind, context, self.system_prompt],
            ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        cache = directory / (fingerprint + ".json")
        if cache.is_file():
            payload = _transport_payload(json.loads(cache.read_text(encoding="utf-8")), kind)
        else:
            prompt = json.dumps({"operation": kind, "task_contract": CONTRACTS[kind],
                                 "transport_limits": {"candidate_count": 3, "candidate_chars": 2400,
                                     "requests": 8, "author_prompt_chars": 6000, "style_chars": 8000},
                                 "source_text": answer, "context": context}, ensure_ascii=False)
            extracted = self.invoke(self.system_prompt, prompt)
            (directory / (fingerprint + ".extraction.md")).write_text(extracted, encoding="utf-8")
            payload = _transport_payload(_answer_payload(extracted), kind)
            if kind == "creator":
                payload = restore_commission_source(answer, payload)
            if kind == "material" and context.get("role") == "event-narrator":
                payload = recover_event_source_status(answer, payload)
            validate_extracted_text(answer, payload, kind, context)
            cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if kind == "creator":
            payload = restore_commission_source(answer, payload)
            payload = resolve_creator_targets(payload, context)
        if kind == "material" and context.get("role") == "event-narrator":
            payload = recover_event_source_status(answer, payload)
        validate_extracted_text(answer, payload, kind, context)
        if kind == "creator":
            payload["source_provenance"] = _commission_provenance(answer, payload)
        cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload


def _transport_payload(payload, kind):
    if payload.get("operation") == kind and isinstance(payload.get("task_contract"), dict):
        delivered = payload["task_contract"]
        if not any(key in payload for key in CONTRACTS[kind]):
            return delivered
    return payload


def validate_extracted_text(answer: str, payload: Mapping[str, Any], kind: str,
                            context: Mapping[str, Any] | None = None) -> None:
    if kind == "card":
        _validate_card_text(answer, payload.get("card") or {})
    if kind == "creator" and payload.get("prose"):
        _verbatim(answer, payload["prose"], "prose")
    if kind == "creator":
        _validate_requested_cards(answer, payload, context or {})
        _commission_provenance(answer, payload)
    if kind == "material":
        _validate_material_text(answer, payload)
        if (context or {}).get("role") == "event-narrator":
            for candidate in payload["candidates"]:
                event_fields(candidate)
    if kind == "tone":
        _validate_tone_text(answer, payload)


def _commission_provenance(answer: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for index, request in enumerate(payload.get("material_requests") or []):
        if not isinstance(request, dict):
            raise ValueError("invalid creator invitation extraction")
        spans = {}
        for key in ("author_prompt", "style_direction"):
            if key not in request or (key == "style_direction" and not request[key]):
                continue
            value = request[key]
            _verbatim(answer, value, key)
            start = answer.index(value)
            spans[key] = {"start": start, "end": start + len(value)}
        rows.append({"request_index": index, "spans": spans})
    return {"source_sha256": sha256(answer.encode("utf-8")).hexdigest(), "requests": rows}


def _validate_tone_text(answer: str, payload: Mapping[str, Any]) -> None:
    edits = payload.get("edits")
    if not isinstance(edits, list):
        raise ValueError("tone extraction needs local edits")
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("tone edit extraction is invalid")
        _verbatim(answer, edit.get("before"), "tone original fragment")
        if edit.get("after"):
            _verbatim(answer, edit["after"], "tone replacement")


def _validate_card_text(answer: str, card: Mapping[str, Any]) -> None:
    sections = card.get("sections")
    if not isinstance(sections, dict) or set(sections) != set(ACTOR_CARD_SECTIONS):
        raise ValueError("card extraction needs all sixteen sections")
    for value in sections.values():
        _verbatim(answer, value, "card section")


def _validate_material_text(answer: str, payload: Mapping[str, Any]) -> None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("material extraction needs candidates")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid material extraction")
        _verbatim(answer, candidate.get("text"), "candidate text")
        for key in ("spoken", "first_person_action", "private_impulse"):
            if candidate.get(key):
                _verbatim(answer, candidate[key], key)


def _validate_requested_cards(answer: str, payload: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    frozen = (context.get("actor_card_context") or {}).get("frozen_scene_cards") or []
    for request in payload.get("material_requests") or []:
        card = request.get("character_card")
        if not card or any(card == item.get("card") for item in frozen):
            continue
        _validate_card_text(answer, card)


def _verbatim(answer: str, value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or value not in answer:
        raise ValueError(f"extraction changed {label}; original natural text is preserved")

