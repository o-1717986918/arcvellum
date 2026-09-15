"""Stable, path-free work identities for Project Agent tools."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any


def work_id_for_root(project_root: Path | str) -> str:
    root = Path(project_root).expanduser().resolve()
    canonical = str(root).replace("\\", "/").casefold()
    return f"work-{sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def work_reference(value: Mapping[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        root = Path(str(value.get("path") or "")).expanduser().resolve()
        return {
            "work_id": work_id_for_root(root),
            "title": str(value.get("title") or root.name),
            "work_type": str(value.get("work_type") or "novel"),
            "status": str(value.get("status") or "planning"),
            "genre": str(value.get("genre") or ""),
            "premise": str(value.get("premise") or "")[:1200],
            "target_length": _integer(value.get("target_length")),
            "read_only": bool(value.get("read_only", False)),
        }
    root = Path(value).expanduser().resolve()
    return {"work_id": work_id_for_root(root), "title": root.name}


def registered_work_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    projects = payload.get("projects")
    return [dict(item) for item in projects if isinstance(item, Mapping)] if isinstance(projects, list) else []


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["registered_work_rows", "work_id_for_root", "work_reference"]
