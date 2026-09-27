"""Distinguish planned scene files from formal prose awaiting migration."""

from __future__ import annotations

from pathlib import Path


def has_unmigrated_formal_work(root: Path) -> bool:
    receipts = root / "workflow" / "scene_commits"
    for draft in (root / "drafts" / "scenes").glob("*.md"):
        if not (receipts / f"{draft.stem}.json").is_file():
            return True
    for delta in (root / "workflow" / "scene_deltas").glob("*.json"):
        if not (receipts / delta.name).is_file():
            return True
    return False


__all__ = ["has_unmigrated_formal_work"]
