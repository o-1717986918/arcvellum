"""Shared clean-result semantics for project-level reviews."""

from __future__ import annotations


def canon_review_is_clean(payload: dict[str, object]) -> bool:
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion not in {"pass", "pass_with_notes"}:
        return False
    return all(
        isinstance(payload.get(field), list) and not payload.get(field)
        for field in (
            "blocking_issues",
            "warnings",
            "unresolved_facts",
            "timeline_risks",
        )
    )


def committee_review_is_clean(payload: dict[str, object]) -> bool:
    recommendation = str(payload.get("final_recommendation") or "").strip().lower()
    if recommendation not in {"approve", "approve_with_notes"}:
        return False
    return all(
        isinstance(payload.get(field), list) and not payload.get(field)
        for field in ("action_items", "disagreements")
    )


__all__ = ["canon_review_is_clean", "committee_review_is_clean"]
