"""Structured scene writeback candidates shared by promotion and state gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WRITEBACK_KEYS = (
    "new_facts",
    "character_changes",
    "relationship_changes",
    "foreshadowing_changes",
    "approval_items",
)


def normalize_writeback_candidates(value: object) -> dict[str, list[str]]:
    mapping = value if isinstance(value, dict) else {}
    result: dict[str, list[str]] = {}
    for key in WRITEBACK_KEYS:
        raw = mapping.get(key)
        items = raw if isinstance(raw, list) else [raw] if isinstance(raw, str) else []
        result[key] = _unique(
            str(item).strip()
            for item in items
            if str(item).strip().casefold() not in {"", "无", "无。", "none", "n/a"}
        )
    return result


def structured_scene_writeback(
    root: Path,
    scene_id: str,
    *,
    candidate_manifest: Path | None = None,
) -> tuple[dict[str, list[str]], str]:
    """Return the freshest structured writeback contract for one scene."""

    candidates: list[tuple[Path, str]] = []
    if candidate_manifest is not None:
        candidates.append((candidate_manifest, "writeback_candidates"))
    candidates.extend(
        [
            (root / "drafts" / "promotions" / f"{scene_id}_promotion.json", "writeback_sections"),
            (root / "drafts" / "compositions" / f"{scene_id}_composition.json", "writeback_candidates"),
        ]
    )
    for path, key in candidates:
        payload = _read_json(path)
        normalized = normalize_writeback_candidates(payload.get(key))
        if any(normalized.values()):
            return normalized, _rel(path, root)
    return normalize_writeback_candidates({}), ""


def merge_writeback_candidates(*values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: _unique(item for value in values for item in value.get(key, []))
        for key in WRITEBACK_KEYS
    }


def has_state_changes(value: dict[str, list[str]]) -> bool:
    return bool(value.get("character_changes") or value.get("relationship_changes"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _unique(items: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:  # type: ignore[union-attr]
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
