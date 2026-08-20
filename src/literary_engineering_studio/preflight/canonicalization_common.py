"""Shared machine-owned metadata operations for preflight canonicalizers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage


def meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    return True


def session_identity(task: TaskPackage, role: str) -> str:
    return f"studio:{role}:{task.task_id}"


def normalize_complete_status(
    payload: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    aliases = {
        "completed": "complete",
        "done": "complete",
        "passed": "complete",
        "handled": "complete",
        "agent_judged": "complete",
        "agent_judgment_complete": "complete",
    }
    status = str(payload.get("status") or "").strip().lower()
    if status in aliases:
        expected["status"] = aliases[status]


def read_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_machine_fields(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    expected: dict[str, Any],
    reason: str,
) -> list[dict[str, str]]:
    changed: list[str] = []
    for field, value in expected.items():
        if not value or payload.get(field) == value:
            continue
        payload[field] = value
        changed.append(field)
    if not changed:
        return []
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return [
        {
            "path": relative,
            "field": field,
            "reason": f"normalized deterministic {reason} metadata",
        }
        for field in changed
    ]


__all__ = [
    "meaningful",
    "normalize_complete_status",
    "read_object",
    "session_identity",
    "write_machine_fields",
]
