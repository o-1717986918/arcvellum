"""Deterministic source contracts for formal export and publication."""

from __future__ import annotations

from ..assets.canon.contracts import CANON_LINT_SOURCE_PATHS


def publish_chapter_source_paths(chapter_id: str) -> tuple[str, ...]:
    """Return every project input read while publishing one chapter."""

    return (
        *CANON_LINT_SOURCE_PATHS,
        f"plot/chapters/{chapter_id}.json",
        f"drafts/chapters/{chapter_id}.md",
        f"exports/{chapter_id}",
        "workflow/approvals/index.jsonl",
        "style",
    )


__all__ = ["publish_chapter_source_paths"]
