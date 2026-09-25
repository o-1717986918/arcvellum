"""Decode lean scene worker JSON without accepting Studio-owned metadata."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    ChangeProposal, CreativeResult, ReviewDecision, ReviewResult, SceneDelta,
)

_MACHINE_FIELDS = frozenset({
    "task_id", "transaction_id", "project_root", "expected_outputs", "completion_marker", "sha256",
})


def _reject_machine_fields(payload: dict[str, Any]) -> None:
    unexpected = sorted(_MACHINE_FIELDS.intersection(payload))
    if unexpected:
        raise ValueError("Pi response contains Studio-owned fields: " + ", ".join(unexpected))


def _proposals(value: Any, *, default_operation: str = "update") -> tuple[ChangeProposal, ...]:
    if not isinstance(value, list):
        return ()
    proposals: list[ChangeProposal] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        pairs = _proposal_attributes(item.get("attributes"))
        target_ref = str(item.get("target_ref") or "").strip()
        summary = str(item.get("summary") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not target_ref and not summary and not evidence and not pairs:
            continue
        proposals.append(ChangeProposal(
            target_ref=target_ref,
            summary=summary,
            evidence=evidence,
            operation=str(item.get("operation") or default_operation).strip(),
            attributes=pairs,
        ))
    return tuple(proposals)


def _proposal_attributes(value: Any) -> tuple[tuple[str, str], ...]:
    if isinstance(value, dict):
        return tuple((str(key), str(entry)) for key, entry in value.items())
    if isinstance(value, list):
        return tuple(
            (str(pair[0]), str(pair[1]))
            for pair in value
            if isinstance(pair, list) and len(pair) == 2
        )
    return ()


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    strings: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = next(
                (
                    str(item.get(key) or "").strip()
                    for key in ("handoff", "summary", "content", "text", "description")
                    if str(item.get(key) or "").strip()
                ),
                "",
            )
        else:
            text = ""
        if text:
            strings.append(text)
    return tuple(strings)


def _answer_payload(answer: str) -> dict[str, Any]:
    text = answer.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else text
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise ValueError("Pi scene response is not a JSON object")
        try:
            value, end = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Pi scene response is not a JSON object") from exc
        if text[start + end:].strip():
            raise ValueError("Pi scene response contains text after its JSON object")
    if not isinstance(value, dict):
        raise ValueError("Pi scene response must be a JSON object")
    return value


def creative_result_from_payload(payload: dict[str, Any]) -> CreativeResult:
    _reject_machine_fields(payload)
    prose = str(payload.get("prose") or "").strip()
    summary = str(payload.get("decision_summary") or "").strip()
    if not prose or not summary:
        raise ValueError("Pi scene result requires prose and decision_summary")
    delta = payload.get("scene_delta")
    values = delta if isinstance(delta, dict) else {}
    return CreativeResult(
        prose=prose,
        decision_summary=summary,
        scene_delta=SceneDelta(
            character_changes=_proposals(values.get("character_changes")),
            canon_candidates=_proposals(values.get("canon_candidates")),
            continuity_changes=_proposals(values.get("continuity_changes")),
            promise_updates=_proposals(values.get("promise_updates")),
            reader_question_updates=_proposals(values.get("reader_question_updates")),
            next_handoff=_strings(values.get("next_handoff")),
            new_asset_candidates=_proposals(
                values.get("new_asset_candidates"), default_operation="create",
            ),
        ),
        decision_trace=_strings(payload.get("decision_trace")),
        escalation_reasons=_strings(payload.get("escalation_reasons")),
    )


def review_result_from_payload(payload: dict[str, Any]) -> ReviewResult:
    _reject_machine_fields(payload)
    try:
        decision = ReviewDecision(str(payload.get("decision") or "").strip().lower())
    except ValueError as exc:
        raise ValueError("Pi scene review decision must be pass, revise, or escalate") from exc
    return ReviewResult(
        decision=decision,
        summary=str(payload.get("summary") or "").strip(),
        revision_instructions=_strings(payload.get("revision_instructions")),
        evidence=_strings(payload.get("evidence")),
    )


__all__ = ["_answer_payload", "creative_result_from_payload", "review_result_from_payload"]
