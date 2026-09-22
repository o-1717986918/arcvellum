"""Narrow Project Agent adapter for append-only chapter planning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def chapter_extension_action(
    extend_chapter: Callable[..., dict[str, Any]],
    invalidate_project: Callable[[Path, str], Any] | None,
) -> Callable[[Path, Mapping[str, Any]], Mapping[str, Any]]:
    def execute(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        chapter_id = str(arguments.get("chapter_id") or "").strip()
        if not chapter_id:
            raise ValueError("project_chapter_extend requires chapter_id")
        result = extend_chapter(
            root,
            chapter_id=chapter_id,
            additional_scenes=int(arguments.get("additional_scenes") or 0),
            target_per_scene=int(arguments.get("target_per_scene") or 3300),
            direction=str(arguments.get("direction") or ""),
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-chapter-extend")
        return {
            "ok": True,
            "operation": "extend_chapter",
            **result,
            "receipt": action_receipt("extend_chapter", result),
        }
    return execute


__all__ = ["chapter_extension_action"]
