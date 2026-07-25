"""Resolve optional preloaded inputs for narrative rhythm contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def scene_text_source(path: Path, supplied: str | None) -> str:
    if isinstance(supplied, str):
        return supplied
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def plan_payload_source(path: Path, supplied: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(supplied, dict):
        return supplied
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
