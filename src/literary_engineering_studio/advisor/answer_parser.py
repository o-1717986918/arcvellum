"""Pure compatibility parser for advisor answers and action metadata."""

from __future__ import annotations

import json
import re
from typing import Any

from .contracts import ALLOWED_ACTIONS, METADATA_END, METADATA_MARKER


def parse_answer(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if METADATA_MARKER in candidate:
        message, metadata_text = candidate.split(METADATA_MARKER, 1)
        metadata_text = metadata_text.split(METADATA_END, 1)[0].strip()
        return normalized_answer(message, _metadata_json(metadata_text))
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return normalized_answer(text.strip(), {})
    if not isinstance(payload, dict):
        raise RuntimeError("advisor answer must be an object")
    metadata = _legacy_metadata(payload)
    return normalized_answer(str(payload.get("message") or payload.get("answer") or ""), metadata)


def _metadata_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _legacy_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "evidence": payload.get("evidence") or payload.get("facts") or [],
        "uncertainties": payload.get("uncertainties") or [],
        "suggested_actions": payload.get("suggested_actions") or [],
        "memory": payload.get("memory") or {},
    }
    action = str(payload.get("suggested_next_action") or "").strip()
    if action and not metadata["suggested_actions"]:
        metadata["suggested_actions"] = [
            {"type": "record_direction", "label": "采纳为创作方向", "message": action}
        ]
    return metadata


def normalized_answer(message: str, metadata: dict[str, Any]) -> dict[str, Any]:
    evidence = _evidence(metadata.get("evidence"))
    return {
        "message": message.strip(),
        "answer": message.strip(),
        "evidence": evidence,
        "facts": evidence,
        "uncertainties": [str(item) for item in metadata.get("uncertainties") or [] if str(item).strip()],
        "suggested_actions": _actions(metadata.get("suggested_actions"))[:3],
        "suggested_next_action": "",
        "memory": metadata.get("memory") if isinstance(metadata.get("memory"), dict) else {},
    }


def _evidence(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"statement": str(item["statement"]), "citation": str(item.get("citation") or "")}
        for item in value
        if isinstance(item, dict) and str(item.get("statement") or "").strip()
    ]


def _actions(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    actions: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or str(item.get("type") or "") not in ALLOWED_ACTIONS:
            continue
        action = {key: str(item.get(key) or "") for key in ("type", "label", "target", "message", "route")}
        if action["label"]:
            actions.append(action)
    return actions


__all__ = ["normalized_answer", "parse_answer"]
