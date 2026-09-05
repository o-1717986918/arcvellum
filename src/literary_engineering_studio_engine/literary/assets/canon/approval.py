"""Content-bound approval evidence for Canon patch application."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def patch_requires_approval(payload: dict[str, Any]) -> bool:
    if payload.get("requires_user_approval") is True:
        return True
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return any(
        isinstance(item, dict) and item.get("requires_user_approval") is True
        for item in items
    )


def approval_record_for_run(root: Path, run_id: str) -> dict[str, Any]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, Any] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def approval_matches_patch(approval: dict[str, Any], patch: Path) -> bool:
    if not approval or not patch.is_file():
        return False
    actual = hashlib.sha256(patch.read_bytes()).hexdigest()
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == actual
    try:
        recorded_at = datetime.fromisoformat(
            str(approval.get("recorded_at") or "").replace("Z", "+00:00")
        )
    except ValueError:
        return False
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    modified_at = datetime.fromtimestamp(patch.stat().st_mtime, tz=timezone.utc)
    return modified_at <= recorded_at.astimezone(timezone.utc)


__all__ = [
    "approval_matches_patch",
    "approval_record_for_run",
    "patch_requires_approval",
]
