"""Project Agent adapter for event-first replacement of unwritten scenes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def future_replan_action(
    replan_future: Callable[..., dict[str, Any]],
    invalidate_project: Callable[[Path, str], Any] | None,
) -> Callable[[Path, Mapping[str, Any]], Mapping[str, Any]]:
    def execute(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        raw = arguments.get("chapter_scene_counts")
        if not isinstance(raw, Mapping) or not raw:
            raise ValueError("project_future_replan requires chapter_scene_counts")
        counts = {str(key): int(value) for key, value in raw.items()}
        result = replan_future(
            root,
            chapter_scene_counts=counts,
            direction=str(arguments.get("direction") or ""),
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-future-replan")
        return {
            "ok": True,
            "operation": "future_replan",
            **result,
            "receipt": action_receipt("future_replan", result),
        }
    return execute


__all__ = ["future_replan_action"]
