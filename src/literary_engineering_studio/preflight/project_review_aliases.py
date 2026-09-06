"""Conservative semantic aliases for historical project review artifacts."""

from __future__ import annotations

from typing import Any


def project_review_semantic_aliases(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    expected = _verdict_alias(payload, committee=committee)
    expected.update(_action_alias(payload, committee=committee))
    return expected


def _verdict_alias(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    verdict_field = "final_recommendation" if committee else "conclusion"
    allowed = (
        {"approve", "approve_with_notes", "revise", "reject"}
        if committee
        else {"pass", "pass_with_notes", "revise_required", "reject"}
    )
    if str(payload.get(verdict_field) or "").strip():
        return {}
    for alias in ("verdict", "recommendation"):
        candidate = str(payload.get(alias) or "").strip().lower()
        if candidate in allowed:
            return {verdict_field: candidate}
    return {}


def _action_alias(
    payload: dict[str, Any],
    *,
    committee: bool,
) -> dict[str, Any]:
    action_field = "action_items" if committee else "recommendations"
    current_actions = payload.get(action_field)
    if isinstance(current_actions, list) and current_actions:
        return {}
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    actions = [_actionable_finding(item) for item in findings]
    normalized = [item for item in actions if item]
    return {action_field: normalized} if normalized else {}


def _actionable_finding(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {}
    target = str(item.get("target_path") or item.get("target") or "").strip()
    action = str(item.get("action") or "").strip()
    verification = str(item.get("verification") or "").strip()
    if not target or not action or not verification:
        return {}
    normalized = {
        "target_path": target,
        "action": action,
        "verification": verification,
    }
    if str(item.get("id") or "").strip():
        normalized["id"] = str(item["id"]).strip()
    return normalized


__all__ = ["project_review_semantic_aliases"]
