"""Shared readiness projection for a current, sealed scene promotion."""

from __future__ import annotations

import hashlib
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
    conclusion, exact_draft = static_review_evidence(review, draft)
    if not conclusion or not exact_draft:
        return "needs_review", (
            "historically promoted draft lacks an exact post-promotion static review",
        )
    if conclusion == "pass":
        return "ready", ()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        return "needs_revision", (f"post-promotion static review is {conclusion}",)
    return "blocked", (f"post-promotion static review conclusion is {conclusion}",)


def static_review_evidence(review: Path, draft: Path) -> tuple[str, bool]:
    """Return the review conclusion and exact promoted-draft binding."""

    if not review.is_file() or not draft.is_file():
        return "", False
    text = review.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        text,
        re.IGNORECASE,
    )
    digest = re.search(
        r"(?m)^-\s*审查对象 SHA-256：`([0-9a-fA-F]{64})`\s*$",
        text,
    )
    conclusion = match.group(1).strip().lower() if match else ""
    exact = bool(
        digest
        and digest.group(1).lower() == hashlib.sha256(draft.read_bytes()).hexdigest()
    )
    return conclusion, exact


__all__ = ["historical_scene_readiness", "static_review_evidence"]
