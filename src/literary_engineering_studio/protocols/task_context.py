"""Consumer-side validation for Engine-owned task context contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


CONTEXT_CONTRACT_SCHEMA = (
    "literary-engineering-workbench/task-context-contract/v1"
)
CONTEXT_CONTRACT_FIELDS = {
    "context_contract_required",
    "context_contract_schema",
    "context_contract_revision",
    "context_contract_status",
    "context_must_inline_paths",
}
CONTEXT_CONTRACT_STATUSES = {"shadow-ready", "bounded-ready"}
CONTEXT_SOURCE_FIELDS = (
    "agent_source_paths",
    "core_managed_outputs",
    "required_reading",
)


def validate_optional_context_contract(
    payload: dict[str, Any],
    *,
    normalize_path: Callable[[str], object],
) -> None:
    present = CONTEXT_CONTRACT_FIELDS & set(payload)
    if not present:
        return
    _validate_header(payload, present)
    normalized = _mandatory_paths(payload, normalize_path)
    allowed = {
        path
        for field in CONTEXT_SOURCE_FIELDS
        for path in _source_paths(payload, field, normalize_path)
    }
    unauthorized = [path for path in normalized if path not in allowed]
    if unauthorized:
        raise ValueError(
            "task package mandatory context is outside the Agent source contract: "
            + ", ".join(unauthorized)
        )
    exact = _optional_tier_paths(
        payload,
        "context_exact_on_demand_paths",
        normalize_path,
    )
    unauthorized_exact = [path for path in exact if path not in allowed]
    if unauthorized_exact:
        raise ValueError(
            "task package exact-on-demand context is outside the Agent source "
            "contract: " + ", ".join(unauthorized_exact)
        )
    overlap = sorted(set(normalized) & set(exact))
    if overlap:
        raise ValueError(
            "task package context tiers overlap: " + ", ".join(overlap)
        )


def _validate_header(payload: dict[str, Any], present: set[str]) -> None:
    if payload.get("context_contract_required") is not True:
        raise ValueError(
            "task package context contract fields require "
            "context_contract_required=true"
        )
    missing = CONTEXT_CONTRACT_FIELDS - present
    if missing:
        raise ValueError(
            "partial task context contract; missing: " + ", ".join(sorted(missing))
        )
    if payload.get("context_contract_schema") != CONTEXT_CONTRACT_SCHEMA:
        raise ValueError("task package context contract schema is invalid")
    if not str(payload.get("context_contract_revision") or "").strip():
        raise ValueError("task package context contract revision is required")
    if payload.get("context_contract_status") not in CONTEXT_CONTRACT_STATUSES:
        raise ValueError("task package context contract status is invalid")


def _mandatory_paths(
    payload: dict[str, Any],
    normalize_path: Callable[[str], object],
) -> list[str]:
    values = payload.get("context_must_inline_paths")
    if not isinstance(values, list) or not values:
        raise ValueError(
            "task package context_must_inline_paths must be a non-empty list"
        )
    normalized = [_context_path(item, normalize_path) for item in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError("task package context_must_inline_paths contains duplicates")
    return normalized


def _source_paths(
    payload: dict[str, Any],
    field: str,
    normalize_path: Callable[[str], object],
) -> list[str]:
    values = payload.get(field)
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"task package context source field must be a list: {field}")
    return [_context_path(item, normalize_path) for item in values]


def _optional_tier_paths(
    payload: dict[str, Any],
    field: str,
    normalize_path: Callable[[str], object],
) -> list[str]:
    if field not in payload:
        return []
    values = _source_paths(payload, field, normalize_path)
    if len(values) != len(set(values)):
        raise ValueError(f"task package {field} contains duplicates")
    return values


def _context_path(
    value: object,
    normalize_path: Callable[[str], object],
) -> str:
    text = str(value or "").strip().replace("\\", "/")
    normalized = str(normalize_path(text))
    if text.endswith("/"):
        raise ValueError(f"task package context path must identify a file: {value}")
    return normalized
