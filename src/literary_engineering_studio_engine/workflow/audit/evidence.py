"""Small review evidence predicates shared by route audit modules."""
from __future__ import annotations

from pathlib import Path


def _review_needs_revision(payload: dict) -> bool:
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        return True
    for key in ("revision_actions", "warnings", "style_notes", "blocking_issues"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return True
    budget_status = _word_budget_adherence_status(payload)
    if budget_status not in {"", "pass", "not_required"}:
        return True
    budget = payload.get("word_budget_adherence")
    if isinstance(budget, dict) and budget_status in {"pass", "not_required"} and budget.get("narrative_load_satisfied") is False:
        return True
    return False


def _mounted_style_exists(root: Path) -> bool:
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        return True
    return bool(list((root / "style" / "mounted").glob("*"))) if (root / "style" / "mounted").exists() else False


def _style_adherence_status(payload: dict) -> str:
    adherence = payload.get("style_adherence")
    if not isinstance(adherence, dict):
        return ""
    return str(adherence.get("status") or "").strip().lower()


def _word_budget_adherence_status(payload: dict) -> str:
    adherence = payload.get("word_budget_adherence")
    if not isinstance(adherence, dict):
        return ""
    return str(adherence.get("status") or "").strip().lower()


def _agent_review_canon_writeback_ok(payload: dict) -> tuple[bool, str]:
    value = payload.get("canon_writeback") if isinstance(payload, dict) else None
    if not isinstance(value, dict):
        return False, "canon_writeback object missing"
    status = str(value.get("status") or "").strip().lower()
    change = _canon_change_value(value.get("canon_change"))
    if status not in {"pass", "not_required", "pending_canon_evolve", "unknown"}:
        return False, f"status={status or 'missing'}"
    if change is False:
        reason = str(value.get("no_canon_change_reason") or "").strip()
        if not reason:
            return False, "canon_change=false requires no_canon_change_reason"
        return True, "no canon change"
    if change in {True, "unknown"}:
        return True, "canon-evolve required or pending"
    return False, "canon_change must be true, false, or unknown"


def _canon_change_value(value: object) -> bool | str | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1", "changed", "change"}:
        return True
    if text in {"false", "no", "0", "none", "no_change", "not_required"}:
        return False
    if text in {"unknown", "pending", "todo", "needs_review"}:
        return "unknown"
    return None
