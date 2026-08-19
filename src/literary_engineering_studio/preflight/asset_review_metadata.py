"""Deterministic shape normalization for Agent-authored asset reviews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ASSET_REVIEW_AGENT_FIELDS = (
    "status",
    "checked",
    "blocking_issues",
    "warnings",
    "revision_actions",
    "promotion_risks",
    "conclusion",
    "reviewed_at",
)


def flatten_asset_review_envelope(
    path: Path,
    relative: str,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Unwrap an otherwise valid review emitted under a generic ``review`` key."""

    nested = payload.get("review")
    if not isinstance(nested, dict):
        return []
    conflicts = {
        field
        for field in ASSET_REVIEW_AGENT_FIELDS
        if field in payload and field in nested and payload[field] != nested[field]
    }
    if conflicts:
        return []
    moved = [field for field in ASSET_REVIEW_AGENT_FIELDS if field not in payload and field in nested]
    if not moved:
        return []
    for field in moved:
        payload[field] = nested[field]
    payload.pop("review", None)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [
        {
            "path": relative,
            "field": field,
            "reason": "flattened unambiguous asset-review response envelope",
        }
        for field in moved
    ]


def canonicalize_asset_review_action_targets(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    candidate_rel: str,
) -> list[dict[str, str]]:
    """Attach the task-owned candidate path to a reviewer's bare field anchor."""

    if not candidate_rel:
        return []
    actions = payload.get("revision_actions")
    if not isinstance(actions, list):
        return []
    changed = False
    for action in actions:
        if not isinstance(action, dict):
            continue
        target = str(action.get("target") or "").replace("\\", "/").strip()
        if not target or target.startswith(candidate_rel):
            continue
        if target.startswith("#"):
            action["target"] = candidate_rel + target
            changed = True
        elif "/" not in target:
            action["target"] = f"{candidate_rel}#{target}"
            changed = True
    if not changed:
        return []
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [
        {
            "path": relative,
            "field": "revision_actions.target",
            "reason": "attached task-owned candidate path to review field anchor",
        }
    ]
