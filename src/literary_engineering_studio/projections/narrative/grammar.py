"""Spatial grammar selection kept separate from projection assembly."""

from __future__ import annotations

from typing import Any


SPATIAL_GRAMMARS = {"spine", "braid", "strata", "constellation", "loop", "stage"}


def resolve_grammar(value: str, base: dict[str, Any]) -> str:
    if value in SPATIAL_GRAMMARS:
        return value
    nodes = [item for item in base.get("nodes", []) if isinstance(item, dict)]
    if str(base.get("level")) == "scene":
        return "stage"
    branch_count = sum(1 for item in nodes if item.get("type") == "branch")
    character_count = sum(1 for item in nodes if item.get("type") == "character")
    question_count = sum(1 for item in nodes if item.get("type") in {"reader-question", "promise"})
    if branch_count >= 3 or character_count >= 5:
        return "braid"
    if question_count >= 4:
        return "constellation"
    return "spine"
