"""Formal-mode safety helpers shared by CLI and API surfaces."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


BYPASS_ARG_NAMES = {
    "allow_unreviewed": "--allow-unreviewed",
    "allow_review_notes": "--allow-review-notes",
    "allow_unapproved": "--allow-unapproved",
    "allow_unresolved": "--allow-unresolved",
    "allow_missing_composition": "--allow-missing-composition",
    "allow_unselected_composition": "--allow-unselected-composition",
    "allow_recommended_branch": "--allow-recommended-branch",
    "allow_missing_branch": "--allow-missing-branch",
    "include_blocked": "--include-blocked",
}


class FormalModeBypassError(RuntimeError):
    """Raised when a formal host tries to use maintainer/debug bypasses."""


def maintainer_mode_enabled() -> bool:
    return os.environ.get("LEW_MAINTAINER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def bypass_hits(values: Mapping[str, Any] | object) -> list[str]:
    if maintainer_mode_enabled():
        return []
    hits: list[str] = []
    for key, flag in BYPASS_ARG_NAMES.items():
        value = values.get(key) if isinstance(values, Mapping) else getattr(values, key, None)
        if value is True:
            hits.append(flag)
    return hits


def ensure_no_bypass(values: Mapping[str, Any] | object, *, surface: str = "formal host") -> None:
    hits = bypass_hits(values)
    if hits:
        raise FormalModeBypassError(formal_bypass_message(hits, surface=surface))


def formal_bypass_message(hits: list[str], *, surface: str = "formal host") -> str:
    flags = ", ".join(hits)
    return (
        f"{surface} blocked maintainer/debug bypass flag(s): {flags}. "
        "Formal Skill-host work must complete the review/approval/task gates instead. "
        "Set LEW_MAINTAINER_MODE=1 only for explicit internal maintenance or regression tests."
    )
