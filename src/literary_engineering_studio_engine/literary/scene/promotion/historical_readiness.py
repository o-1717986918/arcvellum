"""Shared readiness projection for a current, sealed scene promotion."""

from __future__ import annotations

import re
from pathlib import Path

from ....foundation.draft_text import final_body_from_draft_text
from .historical import validate_historical_promotion


def historical_scene_readiness(
    root: Path,
    scene_id: str,
) -> tuple[str, tuple[str, ...]] | None:
    """Return sealed readiness, or None when current-policy checks are required."""

    validation = validate_historical_promotion(root, scene_id)
    if not validation.passed or not validation.current:
        return None
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    review = root / "reviews" / f"{scene_id}-review.md"
    if not draft.is_file():
        return "needs_draft", ("historically promoted draft is missing",)
    body = final_body_from_draft_text(
        draft.read_text(encoding="utf-8", errors="ignore")
    )
    if not body.strip():
        return "needs_draft", ("historically promoted draft body is empty",)
    conclusion = _static_review_conclusion(review)
    if not conclusion:
        return "needs_review", (
            "historically promoted draft lacks its post-promotion static review",
        )
    if conclusion == "pass":
        return "ready", ()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        return "needs_revision", (f"post-promotion static review is {conclusion}",)
    return "blocked", (f"post-promotion static review conclusion is {conclusion}",)


def _static_review_conclusion(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""


__all__ = ["historical_scene_readiness"]
