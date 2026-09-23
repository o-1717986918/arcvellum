"""Decode lean scene worker JSON without accepting Studio-owned metadata."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.literary import ChangeProposal

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
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Pi scene response is not a JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("Pi scene response must be a JSON object")
    return value


__all__ = ["_answer_payload", "_proposals", "_reject_machine_fields", "_strings"]
