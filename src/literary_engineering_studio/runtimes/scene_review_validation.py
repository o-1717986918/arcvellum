"""Source validation for extracted natural-language scene reviews."""

from __future__ import annotations

from typing import Any, Mapping


_ISSUE_PROGRESS = {"resolved", "persists", "changed", "uncertain"}


def validate_review_extraction(payload: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    prose = str(context.get("prose") or "")
    open_ids = _open_issue_ids(context)
    for group, evidence_required in (("strengths", True), ("major_issues", True),
                                     ("optional_explorations", False)):
        _validate_findings(payload.get(group) or [], group, evidence_required, prose, open_ids)
    _validate_progress(payload.get("issue_progress") or [], prose, open_ids)


def _open_issue_ids(context: Mapping[str, Any]) -> set[str]:
    continuity = context.get("review_continuity") or {}
    return {str(item.get("issue_id") or "") for item in continuity.get("open_issues") or []
            if isinstance(item, Mapping) and item.get("issue_id")}


def _validate_findings(rows: Any, group: str, required: bool, prose: str, open_ids: set[str]) -> None:
    if not isinstance(rows, list):
        raise ValueError(f"review extraction {group} must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"review extraction {group} contains an invalid item")
        evidence = str(row.get("evidence") or "")
        if required and not evidence.strip():
            raise ValueError(f"review {group} needs exact prose evidence")
        _validate_current_evidence(evidence, prose, f"review {group} evidence")
        _validate_prior_issue_link(str(row.get("prior_issue_id") or ""), open_ids)


def _validate_progress(rows: Any, prose: str, open_ids: set[str]) -> None:
    if not isinstance(rows, list):
        raise ValueError("review issue progress must be a list")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("review issue progress contains an invalid item")
        identifier = str(row.get("issue_id") or "")
        status = str(row.get("status") or "")
        if identifier not in open_ids or identifier in seen:
            raise ValueError("review issue progress must reference each current open issue once")
        if status not in _ISSUE_PROGRESS:
            raise ValueError("review issue progress status is invalid")
        seen.add(identifier)
        _validate_current_evidence(str(row.get("evidence") or ""), prose,
                                   "review issue progress evidence")


def _validate_prior_issue_link(identifier: str, open_ids: set[str]) -> None:
    if identifier and identifier not in open_ids:
        raise ValueError("review issue link is outside the open issue list")


def _validate_current_evidence(evidence: str, prose: str, label: str) -> None:
    if evidence and evidence not in prose:
        raise ValueError(f"{label} must quote the current prose exactly")


__all__ = ["validate_review_extraction"]
