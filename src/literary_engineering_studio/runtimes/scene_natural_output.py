"""Natural answers are archived before a separate, tool-free transport extraction."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .pi_scene_payload import _answer_payload
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS

NATURAL_RESPONSE_MODE = "natural-v1"
STYLE_TOKEN = "{{STYLE_DIRECTION}}"
_CREATOR_CONTRACT = {
    "material_plan": {"required_kinds": ["one or more of the five kind IDs"], "reason": "creator reason"},
    "material_requests": [{"kind": "actor/environment/character-description/event-narration/scene-description",
        "target": "target", "purpose": "purpose", "scene_moment": "moment", "cue": "stimulus",
        "author_prompt": "creator's invitation", "style_direction": "free style for nonactor",
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
    return "\n\n".join(str(item.get("content") or "").strip()
                        for key in ("author_directive", "mounted")
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
        fingerprint = sha256(json.dumps([kind, context, self.system_prompt],
            ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        cache = directory / (fingerprint + ".json")
        if cache.is_file():
            payload = json.loads(cache.read_text(encoding="utf-8"))
        else:
            prompt = json.dumps({"operation": kind, "task_contract": CONTRACTS[kind],
                                 "transport_limits": {"candidate_count": 3, "candidate_chars": 2400,
                                     "requests": 8, "author_prompt_chars": 6000, "style_chars": 8000},
                                 "source_text": answer, "context": context}, ensure_ascii=False)
            extracted = self.invoke(self.system_prompt, prompt)
            (directory / (fingerprint + ".extraction.md")).write_text(extracted, encoding="utf-8")
            payload = _answer_payload(extracted)
            validate_extracted_text(answer, payload, kind, context)
            cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        validate_extracted_text(answer, payload, kind, context)
        return payload


def validate_extracted_text(answer: str, payload: Mapping[str, Any], kind: str,
                            context: Mapping[str, Any] | None = None) -> None:
    if kind == "card":
        _validate_card_text(answer, payload.get("card") or {})
    if kind == "creator" and payload.get("prose"):
        _verbatim(answer, payload["prose"], "prose")
    if kind == "creator":
        _validate_requested_cards(answer, payload, context or {})
    if kind == "material":
        _validate_material_text(answer, payload)


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

