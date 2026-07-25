"""Adapter between v3 focus levels and the stable v2 graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..narrative_projection import build_narrative_projection


def build_compatible_base(
    config: dict[str, Any],
    project_root: Path,
    level: str,
    focus: str,
    dashboard_payload: dict[str, Any] | None,
    library_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    base_level = level if level in {"book", "chapter", "scene"} else "book"
    return build_narrative_projection(
        config,
        project_root,
        level=base_level,
        focus=focus,
        dashboard_payload=dashboard_payload,
        library_payload=library_payload,
    )


def requested_focus(focus: str, base: dict[str, Any]) -> str:
    return focus if focus else str(base.get("focus") or "")
