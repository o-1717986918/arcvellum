"""Shared validation primitives for creative plan persistence."""

from __future__ import annotations


def validate_plan_id(plan_id: str) -> None:
    if not plan_id.startswith("plan-") or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in plan_id
    ):
        raise ValueError(f"invalid creative plan id: {plan_id}")


def positive_revision(value: object) -> int:
    revision = int(value or 0)
    if revision < 1:
        raise ValueError("creative plan revision must be positive")
    return revision


def project_key(project_root: str) -> str:
    value = str(project_root or "").strip().replace("\\", "/").rstrip("/")
    if not value:
        raise ValueError("creative plan project root must not be empty")
    return value.casefold()
