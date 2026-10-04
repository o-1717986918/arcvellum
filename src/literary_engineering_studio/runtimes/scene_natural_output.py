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
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS, parse_scene_material_requests_v3

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
                                "end_line": None,
                                "knowledge": "actor: known from role_known_archive/character_known/角色可知区; reference from director_reference_archive/creator_reference/主创参考区; empty otherwise"}],
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
        "private_impulse": "verbatim private impulse when explicitly present in source_text, otherwise empty",
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
_CHANGE = {"target_ref": "reference in context.briefing.scene_brief.source_refs; narrative future handoffs use next_handoff",
           "summary": "stated change",
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
        fingerprint = sha256(json.dumps(["verbatim-commission-v3", kind, context, self.system_prompt],
            ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        cache = directory / (fingerprint + ".json")
        issue = ""
        if cache.is_file():
            try:
                payload = _prepare_transport_payload(answer, json.loads(cache.read_text(encoding="utf-8")), kind, context)
            except ValueError as error:
                issue = str(error)
                payload = self._extract(answer, kind, context, directory, fingerprint, issue)
        else:
            payload = self._extract(answer, kind, context, directory, fingerprint, issue)
        if kind == "creator":
            payload["source_provenance"] = _commission_provenance(answer, payload)
        cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _extract(self, answer, kind, context, directory, fingerprint, issue):
        task = {"operation": kind, "task_contract": CONTRACTS[kind], "source_text": answer, "context": context,
            "transport_limits": {"candidate_count": 3, "candidate_chars": 2400,
                "requests": 8, "author_prompt_chars": 6000, "style_chars": 8000}}
        if kind == "creator":
            task["delivery_modes"] = {
                "prepare": "原文明示等待新一轮取材时，提取当轮待调用邀请，prose 使用空值。",
                "complete": "原文明示交付完成正文时，逐字提取正文；素材取舍、旧邀请和角色卡回顾留在工作记录，material_requests 使用空数组。",
                "selection": "依据本次 source_text 的交付意图选择一个阶段；现有候选与冻结计划帮助识别回顾记录。"}
            task["archive_partition_transport"] = "把原文明确选择的 role_known_archive 与 director_reference_archive 各路径逐条展开为 archive_attachments，逐条保留原分类。原文未明确分类时保留空值，由主创补充。"
        for attempt in range(2):
            if issue:
                task["transport_feedback"] = {"issue": issue,
                    "request": "请用本次 source_text 中连续的原文片段完成整理；可选内容空缺时使用合同空值。"}
            extracted = self.invoke(self.system_prompt, json.dumps(task, ensure_ascii=False))
            sequence = len(list(directory.glob(fingerprint + ".extraction*.md"))) + 1
            suffix = ".extraction.md" if sequence == 1 else f".extraction-{sequence}.md"
            path = directory / (fingerprint + suffix)
            path.write_text(extracted, encoding="utf-8")
            try:
                return _prepare_transport_payload(answer, _answer_payload(extracted), kind, context)
            except ValueError as error:
                issue = str(error)
                path.with_suffix(".failure.json").write_text(json.dumps({"issue": issue}, ensure_ascii=False), encoding="utf-8")
                if attempt == 1:
                    raise


def _prepare_transport_payload(answer, payload, kind, context):
    payload = _transport_payload(payload, kind)
    if kind == "creator":
        payload = restore_commission_source(answer, payload)
        payload = resolve_creator_targets(payload, context)
    if kind == "material" and context.get("role") == "event-narrator":
        payload = recover_event_source_status(answer, payload)
    validate_extracted_text(answer, payload, kind, context)
    if kind == "creator" and "briefing" in context:
        participants = (context["briefing"].get("scene_brief") or {}).get("participants") or []
        parse_scene_material_requests_v3(payload, list(participants))
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
        if payload.get("material_requests"):
            raise ValueError("creator transport mixes completed prose and pending material requests; select the source delivery phase")
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

