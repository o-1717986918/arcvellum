"""Shared value cleanup for evidence projections."""

from __future__ import annotations

from typing import Any


def prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: projected
            for key, item in value.items()
            if not empty(projected := prune_empty(item))
        }
    if isinstance(value, list):
        return [projected for item in value if not empty(projected := prune_empty(item))]
    return value


def empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def positive_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


__all__ = ["positive_int", "prune_empty"]
