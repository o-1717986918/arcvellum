"""Cross-route normalization for Engine-owned task context contracts."""

from __future__ import annotations

from pathlib import PurePosixPath
import re


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
CONTEXT_CONTRACT_FINGERPRINT_FIELDS = (
    "context_contract_required",
    "context_contract_schema",
    "context_contract_revision",
    "context_contract_status",
    "context_must_inline_paths",
    "context_exact_on_demand_paths",
    "context_summary_references",
    "context_excluded_paths",
    "context_evidence_contract",
)
CONTEXT_SOURCE_FIELDS = (
    "agent_source_paths",
    "core_managed_outputs",
    "required_reading",
)
REVIEW_EVIDENCE_DECLARATION_SCHEMA = (
    "literary-engineering-workbench/scene-review-context-declaration/v1"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def normalize_context_contract(task: dict[str, object]) -> None:
    present = CONTEXT_CONTRACT_FIELDS & set(task)
    if not present:
        return
    _validate_header(task, present)
    normalized = _mandatory_paths(task)
    allowed = {
        path
        for field in CONTEXT_SOURCE_FIELDS
        for path in _path_list(task, field)
    }
    unauthorized = [path for path in normalized if path not in allowed]
    if unauthorized:
        raise ValueError(
            "formal task mandatory context is outside the Agent source contract: "
            + ", ".join(unauthorized)
        )
    exact, excluded = _normalized_optional_tiers(
        task,
        allowed=allowed,
        mandatory=normalized,
    )
    task["context_must_inline_paths"] = normalized
    if exact:
        task["context_exact_on_demand_paths"] = exact
    if excluded:
        task["context_excluded_paths"] = excluded
    _normalize_review_evidence_contract(task)


def _normalized_optional_tiers(
    task: dict[str, object],
    *,
    allowed: set[str],
    mandatory: list[str],
) -> tuple[list[str], list[str]]:
    exact = _optional_tier_paths(
        task,
        "context_exact_on_demand_paths",
    )
    excluded = _optional_tier_paths(task, "context_excluded_paths")
    for label, paths in (
        ("exact-on-demand", exact),
        ("excluded", excluded),
    ):
        unauthorized = [path for path in paths if path not in allowed]
        if unauthorized:
            raise ValueError(
                f"formal task {label} context is outside the Agent source "
                "contract: " + ", ".join(unauthorized)
            )
    overlap = sorted(
        (set(mandatory) & set(exact))
        | (set(excluded) & set((*mandatory, *exact)))
    )
    if overlap:
        raise ValueError(
            "formal task context tiers overlap: " + ", ".join(overlap)
        )
    return exact, excluded


def _validate_header(task: dict[str, object], present: set[str]) -> None:
    if task.get("context_contract_required") is not True:
        raise ValueError(
            "formal task context_contract_required must be true when a contract is present"
        )
    missing = CONTEXT_CONTRACT_FIELDS - present
    if missing:
        raise ValueError(
            "formal task has a partial context contract; missing: "
            + ", ".join(sorted(missing))
        )
    if task.get("context_contract_schema") != CONTEXT_CONTRACT_SCHEMA:
        raise ValueError("formal task context contract schema is invalid")
    if not str(task.get("context_contract_revision") or "").strip():
        raise ValueError("formal task context contract revision is required")
    if str(task.get("context_contract_status") or "") not in CONTEXT_CONTRACT_STATUSES:
        raise ValueError("formal task context contract status is invalid")


def _mandatory_paths(task: dict[str, object]) -> list[str]:
    values = task.get("context_must_inline_paths")
    if not isinstance(values, list) or not values:
        raise ValueError(
            "formal task context_must_inline_paths must be a non-empty list"
        )
    normalized = [_normalize_path(item) for item in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError("formal task context_must_inline_paths contains duplicates")
    return normalized


def _path_list(task: dict[str, object], field: str) -> list[str]:
    value = task.get(field)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"formal task context source field must be a list: {field}")
    return [_normalize_path(item) for item in value]


def _optional_tier_paths(
    task: dict[str, object],
    field: str,
) -> list[str]:
    if field not in task:
        return []
    values = _path_list(task, field)
    if len(values) != len(set(values)):
        raise ValueError(f"formal task {field} contains duplicates")
    return values


def _normalize_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("formal task context path must not be empty")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
        or text.endswith("/")
    ):
        raise ValueError(
            f"formal task context path must be a normalized file path: {value}"
        )
    return path.as_posix()


def _normalize_review_evidence_contract(task: dict[str, object]) -> None:
    value = task.get("context_evidence_contract")
    is_current_review = (
        str(task.get("current_state") or "") == "candidate-review"
        and str(task.get("context_contract_revision") or "") == "scene-v2"
    )
    if value is None:
        if is_current_review:
            raise ValueError(
                "candidate-review scene-v2 requires context_evidence_contract"
            )
        return
    declaration = _review_declaration(value, task)
    normalized = _review_paths(declaration)
    _validate_review_path_ownership(task, normalized)
    _validate_review_digests(declaration)
    task["context_evidence_contract"] = {**declaration, **normalized}


def _review_declaration(
    value: object,
    task: dict[str, object],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("context_evidence_contract must be an object")
    if value.get("schema") != REVIEW_EVIDENCE_DECLARATION_SCHEMA:
        raise ValueError("context_evidence_contract schema is invalid")
    for field in ("revision", "scene_id", "output_schema_name"):
        if not str(value.get(field) or "").strip():
            raise ValueError(
                f"context_evidence_contract.{field} is required"
            )
    if str(value.get("scene_id")) != str(task.get("scene_id") or ""):
        raise ValueError(
            "context_evidence_contract scene_id does not match task"
        )
    return value


def _review_paths(value: dict[str, object]) -> dict[str, str]:
    return {
        field: _normalize_path(value.get(field))
        for field in (
            "artifact_path",
            "candidate_path",
            "sidecar_path",
            "review_json_path",
            "review_report_path",
        )
    }


def _validate_review_path_ownership(
    task: dict[str, object],
    normalized: dict[str, str],
) -> None:
    expected = set(_path_list(task, "expected_outputs"))
    core = set(_path_list(task, "core_managed_outputs"))
    sources = set(_path_list(task, "agent_source_paths"))
    if normalized["candidate_path"] not in sources:
        raise ValueError(
            "context_evidence_contract candidate is outside Agent sources"
        )
    for field in ("artifact_path", "sidecar_path"):
        if normalized[field] not in expected or normalized[field] not in core:
            raise ValueError(
                f"context_evidence_contract {field} must be a core-managed output"
            )
    for field in ("review_json_path", "review_report_path"):
        if normalized[field] not in expected:
            raise ValueError(
                f"context_evidence_contract {field} must be an expected output"
            )
    mandatory = set(_path_list(task, "context_must_inline_paths"))
    exact = set(_path_list(task, "context_exact_on_demand_paths"))
    if normalized["artifact_path"] not in mandatory:
        raise ValueError(
            "context_evidence_contract artifact must be mandatory inline"
        )
    if normalized["sidecar_path"] not in exact:
        raise ValueError(
            "context_evidence_contract sidecar must be exact-on-demand"
        )


def _validate_review_digests(value: dict[str, object]) -> None:
    for field in (
        "output_schema_resource_sha256",
        "output_schema_contract_sha256",
    ):
        if not _SHA256.fullmatch(str(value.get(field) or "")):
            raise ValueError(
                f"context_evidence_contract.{field} is invalid"
            )
