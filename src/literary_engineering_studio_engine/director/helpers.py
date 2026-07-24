"""Small deterministic helpers shared by director submodules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _safe_jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _safe_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_safe_jsonable(item) for item in value]
        return str(value)



def _trim_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
