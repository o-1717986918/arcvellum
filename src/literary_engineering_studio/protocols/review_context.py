"""Independent Studio validation for compact scene-review evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping


REVIEW_CONTEXT_SCHEMA = (
    "literary-engineering-workbench/scene-review-context/v1"
)
REVIEW_CONTEXT_REVISION = "2026-07-28.1"
REVIEW_CONTEXT_DECLARATION_SCHEMA = (
    "literary-engineering-workbench/scene-review-context-declaration/v1"
)
SCENE_REVIEW_SCHEMA_NAME = "scene_review.v1"
SCENE_REVIEW_SCHEMA_VALUE = (
    "literary-engineering-workbench/scene-review-agent/v1"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PATH_FIELDS = (
    "artifact_path",
    "candidate_path",
    "sidecar_path",
    "review_json_path",
    "review_report_path",
)


def validate_optional_review_context_declaration(
    payload: dict[str, Any],
    *,
    normalize_path: Callable[[str], object],
) -> None:
    value = payload.get("context_evidence_contract")
    required = (
        str(payload.get("current_state") or "") == "candidate-review"
        and str(payload.get("context_contract_revision") or "") == "scene-v2"
    )
    if value is None:
        if required:
            raise ValueError(
                "candidate-review scene-v2 requires context_evidence_contract"
            )
        return
    declaration = _declaration(value, normalize_path)
    if declaration["scene_id"] != str(payload.get("scene_id") or ""):
        raise ValueError(
            "context_evidence_contract scene_id does not match task"
        )
    expected = _paths(payload.get("expected_outputs"), normalize_path)
    core = _paths(payload.get("core_managed_outputs"), normalize_path)
    sources = _paths(payload.get("agent_source_paths"), normalize_path)
    if declaration["candidate_path"] not in sources:
        raise ValueError(
            "context_evidence_contract candidate is outside Agent sources"
        )
    for field in ("artifact_path", "sidecar_path"):
        path = declaration[field]
        if path not in expected or path not in core:
            raise ValueError(
                f"context_evidence_contract {field} must be a core-managed output"
            )
    for field in ("review_json_path", "review_report_path"):
        if declaration[field] not in expected:
            raise ValueError(
                f"context_evidence_contract {field} must be an expected output"
            )
    _validate_visibility_tiers(
        payload,
        declaration,
        normalize_path=normalize_path,
    )


def _validate_visibility_tiers(
    payload: dict[str, Any],
    declaration: Mapping[str, str],
    *,
    normalize_path: Callable[[str], object],
) -> None:
    mandatory = _paths(
        payload.get("context_must_inline_paths"),
        normalize_path,
    )
    exact = _paths(
        payload.get("context_exact_on_demand_paths"),
        normalize_path,
    )
    if declaration["artifact_path"] not in mandatory:
        raise ValueError(
            "context_evidence_contract artifact must be mandatory inline"
        )
    if declaration["sidecar_path"] not in exact:
        raise ValueError(
            "context_evidence_contract sidecar must be exact-on-demand"
        )


def validate_materialized_review_context(
    payload: dict[str, Any],
    workspace: Path,
    *,
    normalize_path: Callable[[str], object],
    require: bool = False,
) -> None:
    value = payload.get("context_evidence_contract")
    if value is None:
        if require:
            raise ValueError(
                "bounded candidate-review requires compact review evidence"
            )
        return
    declaration = _declaration(value, normalize_path)
    artifact_path = _workspace_path(
        workspace,
        declaration["artifact_path"],
    )
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "compact review evidence is missing or invalid"
        ) from exc
    if not isinstance(artifact, dict):
        raise ValueError("compact review evidence must be an object")
    _validate_artifact_identity(artifact, declaration)
    _validate_candidate_and_sidecar(
        artifact,
        declaration,
        workspace,
    )
    _validate_output_schema(artifact, declaration)
    _validate_evidence_sections(artifact)


def _validate_artifact_identity(
    artifact: Mapping[str, Any],
    declaration: Mapping[str, str],
) -> None:
    if artifact.get("schema") != REVIEW_CONTEXT_SCHEMA:
        raise ValueError("compact review evidence schema is invalid")
    if artifact.get("revision") != REVIEW_CONTEXT_REVISION:
        raise ValueError("compact review evidence revision is invalid")
    if str(artifact.get("scene_id") or "") != declaration["scene_id"]:
        raise ValueError("compact review evidence scene_id is stale")
    outputs = _mapping(artifact.get("review_outputs"))
    if (
        outputs.get("json") != declaration["review_json_path"]
        or outputs.get("markdown") != declaration["review_report_path"]
    ):
        raise ValueError("compact review evidence output paths are stale")


def _validate_candidate_and_sidecar(
    artifact: Mapping[str, Any],
    declaration: Mapping[str, str],
    workspace: Path,
) -> None:
    candidate = _mapping(artifact.get("candidate"))
    sidecar = _mapping(artifact.get("full_sidecar"))
    if candidate.get("path") != declaration["candidate_path"]:
        raise ValueError("compact review evidence candidate path is stale")
    if sidecar.get("path") != declaration["sidecar_path"]:
        raise ValueError("compact review evidence sidecar path is stale")
    if sidecar.get("visibility") != "exact_on_demand":
        raise ValueError(
            "compact review evidence must retain the full sidecar on demand"
        )
    candidate_digest = _file_sha256(
        _workspace_path(workspace, declaration["candidate_path"])
    )
    sidecar_digest = _file_sha256(
        _workspace_path(workspace, declaration["sidecar_path"])
    )
    if candidate.get("sha256") != candidate_digest:
        raise ValueError("compact review evidence candidate digest is stale")
    if sidecar.get("sha256") != sidecar_digest:
        raise ValueError("compact review evidence sidecar digest is stale")
    sources = _mapping(artifact.get("source_digests"))
    if sources.get(declaration["candidate_path"]) != candidate_digest:
        raise ValueError(
            "compact review evidence source digest does not bind the candidate"
        )


def _validate_output_schema(
    artifact: Mapping[str, Any],
    declaration: Mapping[str, str],
) -> None:
    output_schema = _mapping(artifact.get("output_schema"))
    contract = _mapping(output_schema.get("contract"))
    if output_schema.get("name") != SCENE_REVIEW_SCHEMA_NAME:
        raise ValueError("compact review output schema name is invalid")
    if (
        contract.get("schema_id") != SCENE_REVIEW_SCHEMA_NAME
        or contract.get("schema_value") != SCENE_REVIEW_SCHEMA_VALUE
    ):
        raise ValueError("compact review output schema contract is invalid")
    digest = _canonical_sha256(contract)
    if (
        output_schema.get("contract_sha256") != digest
        or declaration["output_schema_contract_sha256"] != digest
    ):
        raise ValueError("compact review output schema digest is stale")
    if (
        output_schema.get("resource_sha256")
        != declaration["output_schema_resource_sha256"]
    ):
        raise ValueError(
            "compact review output schema resource digest is stale"
        )
    for field in ("required", "types", "enums"):
        if not isinstance(
            contract.get(field),
            list if field == "required" else dict,
        ):
            raise ValueError(
                f"compact review output schema is missing {field}"
            )


def _validate_evidence_sections(artifact: Mapping[str, Any]) -> None:
    evidence = _mapping(artifact.get("deterministic_evidence"))
    for field in (
        "style_lint",
        "word_budget",
        "reader_experience",
        "narrative_rhythm",
    ):
        if not isinstance(evidence.get(field), dict):
            raise ValueError(
                f"compact review evidence is missing {field}"
            )
    for field in (
        "style_mount_snapshot",
        "creative_quality_profile",
        "review_policy",
        "source_digests",
    ):
        if not isinstance(artifact.get(field), dict):
            raise ValueError(
                f"compact review evidence is missing {field}"
            )
    policy = _mapping(artifact.get("review_policy"))
    if (
        policy.get("anti_evasion_required") is not True
        or policy.get("independent_reviewer_required") is not True
        or policy.get("canon_writeback_required") is not True
    ):
        raise ValueError("compact review policy is incomplete")


def _declaration(
    value: object,
    normalize_path: Callable[[str], object],
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("context_evidence_contract must be an object")
    if value.get("schema") != REVIEW_CONTEXT_DECLARATION_SCHEMA:
        raise ValueError("context_evidence_contract schema is invalid")
    result = {
        "schema": str(value.get("schema") or ""),
        "revision": str(value.get("revision") or ""),
        "scene_id": str(value.get("scene_id") or ""),
        "output_schema_name": str(value.get("output_schema_name") or ""),
        "output_schema_resource_sha256": str(
            value.get("output_schema_resource_sha256") or ""
        ),
        "output_schema_contract_sha256": str(
            value.get("output_schema_contract_sha256") or ""
        ),
        **{
            field: str(normalize_path(str(value.get(field) or "")))
            for field in _PATH_FIELDS
        },
    }
    if result["revision"] != REVIEW_CONTEXT_REVISION:
        raise ValueError("context_evidence_contract revision is invalid")
    if result["output_schema_name"] != SCENE_REVIEW_SCHEMA_NAME:
        raise ValueError(
            "context_evidence_contract output schema name is invalid"
        )
    for field in (
        "output_schema_resource_sha256",
        "output_schema_contract_sha256",
    ):
        if not _SHA256.fullmatch(result[field]):
            raise ValueError(
                f"context_evidence_contract.{field} is invalid"
            )
    return result


def _paths(
    value: object,
    normalize_path: Callable[[str], object],
) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list):
        raise ValueError("review context path collection must be a list")
    return {str(normalize_path(str(item))) for item in value}


def _workspace_path(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    path = (root / Path(relative)).resolve()
    if not path.is_relative_to(root):
        raise ValueError("compact review evidence path escapes workspace")
    if not path.is_file():
        raise ValueError(
            f"compact review evidence source is missing: {relative}"
        )
    return path


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(payload: object) -> str:
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "REVIEW_CONTEXT_DECLARATION_SCHEMA",
    "REVIEW_CONTEXT_REVISION",
    "REVIEW_CONTEXT_SCHEMA",
    "validate_materialized_review_context",
    "validate_optional_review_context_declaration",
]
