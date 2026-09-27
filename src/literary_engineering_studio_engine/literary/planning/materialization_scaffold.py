"""Recognize untouched scene scaffolds during plan materialization."""

from __future__ import annotations

from pathlib import Path
import re


def is_blank_scene_scaffold(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r'(?m)^scene_id:\s*["\']?\s*["\']?$', text)) and not any(
        (path.parent.parent / relative).exists()
        for relative in (
            f"drafts/scenes/{path.stem}.md",
            f"drafts/candidates/{path.stem}-platform-agent.md",
            f"reviews/agent/{path.stem}_scene_review.json",
        )
    )


__all__ = ["is_blank_scene_scaffold"]
