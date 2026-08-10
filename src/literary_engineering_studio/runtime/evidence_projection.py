"""Loss-preserving structured projections for Prompt v3 evidence."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import PurePosixPath
from typing import Any

from ruamel.yaml import YAML


def project_evidence_body(path: str, body: str, *, fidelity: str) -> str:
    """Remove empty or duplicated transport fields from structured evidence.

    Lossless evidence is never projected.  Structured projections preserve
    values and source identity while removing fields available from a higher
    fidelity source in the same Prompt Program.
    """

    if fidelity != "structured":
        return body
    suffix = PurePosixPath(path).suffix.casefold()
    try:
        if suffix == ".json":
            payload = json.loads(body)
            if path.endswith("scene_review.context.json"):
                payload = _review_context_projection(payload)
            elif path == "style/creative_quality_profile.json":
                payload = _creative_quality_projection(payload)
            return json.dumps(_prune_empty(payload), ensure_ascii=False, separators=(",", ":"))
        if suffix in {".yaml", ".yml"}:
            yaml = YAML(typ="safe")
            payload = yaml.load(body)
            stream = StringIO()
            writer = YAML()
            writer.default_flow_style = False
            writer.allow_unicode = True
            writer.dump(_prune_empty(payload), stream)
            return stream.getvalue().rstrip()
    except (ValueError, TypeError, OSError):
        return body
    return body


def _creative_quality_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        key: value[key]
        for key in (
            "schema",
            "profile_id",
            "name",
            "preset",
            "revision",
            "rule_modes",
            "thresholds",
            "punctuation",
            "custom_banned_phrases",
            "preferred_habits",
            "exceptions",
            "digest",
        )
        if key in value
    }


def _review_context_projection(value: object) -> object:
    if not isinstance(value, dict):
        return value
    deterministic = value.get("deterministic_evidence")
    compact = dict(deterministic) if isinstance(deterministic, dict) else {}
    rhythm = compact.get("narrative_rhythm")
    if isinstance(rhythm, dict):
        compact["narrative_rhythm"] = {
            key: rhythm.get(key)
            for key in (
                "status",
                "missing_required",
                "plan_digest",
                "plan_revision",
                "source",
            )
            if key in rhythm
        }
    budget = compact.get("word_budget")
    if isinstance(budget, dict):
        compact["word_budget"] = {
            key: budget.get(key)
            for key in (
                "status",
                "budget_contract_status",
                "target_chinese_chars",
                "min_chinese_chars",
                "max_chinese_chars",
                "clean_body_chinese_chars",
                "narrative_load",
                "message",
            )
            if key in budget
        }
    return {
        key: _compact_review_schema(item) if key == "output_schema" else item
        for key, item in value.items()
        if key not in {"creative_quality_profile", "source_digests", "style_mount_snapshot"}
    } | {"deterministic_evidence": compact}


def _compact_review_schema(value: object) -> object:
    if not isinstance(value, dict):
        return value
    contract = value.get("contract")
    compact_contract = dict(contract) if isinstance(contract, dict) else {}
    compact_contract["required_type_groups"] = _required_type_groups(
        compact_contract
    )
    compact_contract.pop("recommended", None)
    compact_contract.pop("required", None)
    compact_contract.pop("types", None)
    return {
        key: item
        for key, item in value.items()
        if key != "resource_sha256"
    } | {"contract": compact_contract}


def _required_type_groups(contract: dict[str, Any]) -> dict[str, list[str]]:
    required = contract.get("required")
    field_types = contract.get("types")
    groups: dict[str, list[str]] = {}
    for field in required if isinstance(required, list) else []:
        field_type = field_types.get(field) if isinstance(field_types, dict) else None
        if isinstance(field_type, str):
            groups.setdefault(field_type, []).append(field)
    return groups


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: projected
            for key, item in value.items()
            if not _empty(projected := _prune_empty(item))
        }
    if isinstance(value, list):
        return [projected for item in value if not _empty(projected := _prune_empty(item))]
    return value


def _empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


__all__ = ["project_evidence_body"]
