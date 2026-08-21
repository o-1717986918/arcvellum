"""Compact semantic review evidence without weakening review contracts."""

from __future__ import annotations

from typing import Any


def review_context(value: object) -> object:
    if not isinstance(value, dict):
        return value
    deterministic = value.get("deterministic_evidence")
    compact = dict(deterministic) if isinstance(deterministic, dict) else {}
    rhythm = compact.get("narrative_rhythm")
    if isinstance(rhythm, dict):
        compact["narrative_rhythm"] = _select(
            rhythm, "status", "missing_required", "plan_digest", "plan_revision", "source"
        )
    budget = compact.get("word_budget")
    if isinstance(budget, dict):
        compact["word_budget"] = _select(
            budget,
            "status", "budget_contract_status", "target_chinese_chars", "min_chinese_chars",
            "max_chinese_chars", "clean_body_chinese_chars", "narrative_load", "message",
        )
    return {
        key: compact_review_schema(item) if key == "output_schema" else item
        for key, item in value.items()
        if key not in {"creative_quality_profile", "source_digests", "style_mount_snapshot"}
    } | {"deterministic_evidence": compact}


def revision_review(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return _select(
        value,
        "schema", "schema_id", "scene_id", "candidate_path", "candidate_sha256", "conclusion",
        "blocking_issues", "warnings", "revision_actions", "style_notes",
    ) | {
        "style_adherence": _nested_select(value, "style_adherence", "status", "deviations"),
        "word_budget_adherence": _nested_select(
            value,
            "word_budget_adherence",
            "status", "target_chinese_chars", "min_chinese_chars", "max_chinese_chars",
            "clean_body_chinese_chars",
        ),
        "revision_integrity": _nested_select(
            value, "revision_integrity", "required", "reason", "route"
        ),
    }


def committee_longform_audit(value: object) -> object:
    """Keep literary audit evidence while collapsing Core-owned provenance."""

    if not isinstance(value, dict):
        return value
    snapshot = value.get("input_snapshot")
    compact_snapshot = (
        _select(snapshot, "digest", "file_count")
        if isinstance(snapshot, dict)
        else {}
    )
    return _select(
        value,
        "schema",
        "summary",
        "word_budget",
        "rhythm_curves",
        "macro_rhythm",
        "continuity_ledgers",
        "scenes",
        "characters",
        "foreshadowing",
        "issues",
    ) | {"input_snapshot": compact_snapshot}


def compact_review_schema(value: object) -> object:
    if not isinstance(value, dict):
        return value
    contract = value.get("contract")
    compact_contract = dict(contract) if isinstance(contract, dict) else {}
    compact_contract["required_type_groups"] = _required_type_groups(compact_contract)
    for key in ("recommended", "required", "types"):
        compact_contract.pop(key, None)
    return {key: item for key, item in value.items() if key != "resource_sha256"} | {
        "contract": compact_contract
    }


def _nested_select(value: dict, field: str, *keys: str) -> dict:
    nested = value.get(field)
    return _select(nested, *keys) if isinstance(nested, dict) else {}


def _select(value: dict, *keys: str) -> dict:
    return {key: value[key] for key in keys if key in value}


def _required_type_groups(contract: dict[str, Any]) -> dict[str, list[str]]:
    required = contract.get("required")
    field_types = contract.get("types")
    groups: dict[str, list[str]] = {}
    for field in required if isinstance(required, list) else []:
        field_type = field_types.get(field) if isinstance(field_types, dict) else None
        if isinstance(field_type, str):
            groups.setdefault(field_type, []).append(field)
    return groups


__all__ = [
    "committee_longform_audit",
    "compact_review_schema",
    "review_context",
    "revision_review",
]
