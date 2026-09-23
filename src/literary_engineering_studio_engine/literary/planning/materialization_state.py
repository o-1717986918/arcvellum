"""Formal-output state checks used while materializing scene contracts."""

from __future__ import annotations

from pathlib import Path


def has_formal_scene_output(root: Path, scene_id: str) -> bool:
    return any(
        (root / relative).is_file()
        for relative in (
            f"drafts/scenes/{scene_id}.md",
            f"workflow/scene_commits/{scene_id}.json",
            f"workflow/scene_deltas/{scene_id}.json",
        )
    )


__all__ = ["has_formal_scene_output"]
