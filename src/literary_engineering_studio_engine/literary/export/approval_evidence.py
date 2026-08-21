"""Project-relative evidence contract for a chapter release decision."""

from __future__ import annotations


def release_approval_evidence_paths(chapter_id: str) -> tuple[str, ...]:
    """Return bounded release evidence in Creative Steward priority order."""

    prefix = f"exports/{chapter_id}/{chapter_id}"
    return (
        f"exports/{chapter_id}/export_manifest.json",
        f"{prefix}_novel.inspection.json",
        f"{prefix}_screenplay.inspection.json",
        f"{prefix}_video_prompt_pack.inspection.json",
        "reviews/longform/longform_audit.json",
        f"{prefix}_novel.md",
        f"plot/chapters/{chapter_id}.json",
        "reviews/agent/committee_project-final-audit.json",
    )


__all__ = ["release_approval_evidence_paths"]
