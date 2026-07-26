"""Evidence-bound contracts between archaeology fan-in and Archive candidates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ...agent_schema import validate_payload
from ..assets.registry import ASSET_SCHEMA_NAMES
from .evidence import canonical_digest


IDENTITY_RESOLUTION_SCHEMA = "arcvellum/project-archaeology-identity-resolution/v1"
RECONSTRUCTION_CANDIDATE_SCHEMA = "arcvellum/project-archaeology-reconstruction-candidate/v1"
DOMAIN_REVIEW_SCHEMA = "arcvellum/project-archaeology-domain-review/v1"
MATERIALIZATION_SCHEMA = "arcvellum/project-archaeology-materialization/v1"

ARCHAEOLOGY_DOMAINS = ("character", "world", "plot", "style", "promise")
IDENTITY_RESOLUTIONS = {"single", "merge", "keep_distinct", "partial", "unresolved"}
CONFLICT_DISPOSITIONS = {"resolved", "partially_resolved", "unresolved", "not_applicable"}
REVIEW_STATUSES = {"pass", "revise_required", "blocked"}
ASSET_DECISIONS = {"promote", "hold", "reject", "analysis_only"}
PROMOTION_RECOMMENDATIONS = {"promote", "hold", "analysis_only"}


def reconstruction_paths(import_dir: str | Path) -> dict[str, str]:
    base = Path(import_dir).as_posix().rstrip("/")
    folder = f"{base}/reconstruction"
    return {
        "resolution_task": f"{folder}/identity_resolution.agent_tasks.md",
        "resolution": f"{folder}/identity_resolution.json",
        "resolution_report": f"{folder}/identity_resolution.md",
        "resolution_completion": f"{folder}/identity_resolution.agent_completion.json",
        "candidate_task": f"{folder}/candidate_project.agent_tasks.md",
        "candidate": f"{folder}/candidate_project.json",
        "candidate_report": f"{folder}/candidate_project.md",
        "candidate_completion": f"{folder}/candidate_project.agent_completion.json",
        "review_task": f"{folder}/domain_review.agent_tasks.md",
        "review": f"{folder}/domain_review.json",
        "review_report": f"{folder}/domain_review.md",
        "review_completion": f"{folder}/domain_review.agent_completion.json",
        "materialization": f"{folder}/materialization_manifest.json",
        "materialization_report": f"{folder}/materialization_manifest.md",
    }


def validate_identity_resolution(
    payload: dict[str, Any],
    *,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
) -> list[str]:
    errors = _identity_errors(
        payload,
        schema=IDENTITY_RESOLUTION_SCHEMA,
        work_id=str(manifest.get("work_id") or ""),
        aggregate_revision=str(aggregate.get("revision") or ""),
        evidence_revision=_evidence_revision(manifest),
        status="complete",
    )
    occurrences = {
        str(item.get("candidate_ref") or "")
        for item in aggregate.get("entity_occurrences") or []
        if isinstance(item, dict) and str(item.get("candidate_ref") or "")
    }
    groups = payload.get("entity_groups")
    if not isinstance(groups, list):
        return [*errors, "identity resolution entity_groups must be a list"]
    group_errors, seen_refs = _entity_group_errors(groups, occurrences)
    errors.extend(group_errors)
    errors.extend(_occurrence_coverage_errors(occurrences, seen_refs))
    errors.extend(_conflict_review_errors(payload, aggregate))
    return errors


def _entity_group_errors(
    groups: list[object],
    occurrences: set[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    seen_refs: list[str] = []
    seen_ids: set[str] = set()
    for index, group in enumerate(groups):
        item_errors, entity_id, refs = _entity_group_item_errors(
            group,
            index=index,
            occurrences=occurrences,
            seen_ids=seen_ids,
        )
        errors.extend(item_errors)
        if entity_id:
            seen_ids.add(entity_id)
        seen_refs.extend(refs)
    return errors, seen_refs


def _entity_group_item_errors(
    group: object,
    *,
    index: int,
    occurrences: set[str],
    seen_ids: set[str],
) -> tuple[list[str], str, list[str]]:
    prefix = f"entity_groups[{index}]"
    if not isinstance(group, dict):
        return [f"{prefix} must be an object"], "", []
    errors: list[str] = []
    entity_id = str(group.get("entity_id") or "")
    if not _safe_id(entity_id):
        errors.append(f"{prefix}.entity_id must be a stable safe id")
    if entity_id in seen_ids:
        errors.append(f"duplicate resolved entity_id: {entity_id}")
    resolution = str(group.get("resolution") or "")
    if resolution not in IDENTITY_RESOLUTIONS:
        errors.append(f"{prefix}.resolution must be one of {sorted(IDENTITY_RESOLUTIONS)}")
    refs = _string_list(group.get("occurrence_refs"))
    if not refs:
        errors.append(f"{prefix}.occurrence_refs must be non-empty")
    unknown = sorted(set(refs) - occurrences)
    if unknown:
        errors.append(f"{prefix}.occurrence_refs contains unknown refs: {', '.join(unknown)}")
    errors.extend(_evidence_judgment_errors(group, prefix))
    return errors, entity_id, refs


def _occurrence_coverage_errors(
    occurrences: set[str],
    seen_refs: list[str],
) -> list[str]:
    errors: list[str] = []
    duplicates = sorted({item for item in seen_refs if seen_refs.count(item) > 1})
    missing = sorted(occurrences - set(seen_refs))
    if duplicates:
        errors.append("identity resolution assigns occurrences more than once: " + ", ".join(duplicates))
    if missing:
        errors.append("identity resolution omits entity occurrences: " + ", ".join(missing))
    return errors


def validate_reconstruction_candidate(
    payload: dict[str, Any],
    *,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    resolution: dict[str, Any],
) -> list[str]:
    mode = str(manifest.get("mode") or "")
    errors = _identity_errors(
        payload,
        schema=RECONSTRUCTION_CANDIDATE_SCHEMA,
        work_id=str(manifest.get("work_id") or ""),
        mode=mode,
        aggregate_revision=str(aggregate.get("revision") or ""),
        resolution_revision=str(resolution.get("revision") or ""),
        status="candidate",
    )
    if str(resolution.get("revision") or "") != canonical_digest(resolution):
        errors.append("identity resolution revision does not match its content")
    errors.extend(_project_summary_errors(payload.get("project_summary")))
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return [*errors, "reconstruction assets must be a list"]
    evidence_refs = _aggregate_evidence_refs(aggregate)
    errors.extend(
        _reconstruction_asset_errors(
            assets,
            mode=mode,
            evidence_refs=evidence_refs,
        )
    )
    errors.extend(_domain_observation_errors(payload, evidence_refs))
    return errors


def _project_summary_errors(summary: object) -> list[str]:
    if not isinstance(summary, dict):
        return ["reconstruction project_summary must be an object"]
    errors = [
        f"reconstruction project_summary.{field} is required"
        for field in ("title", "premise")
        if not str(summary.get(field) or "").strip()
    ]
    if not isinstance(summary.get("unknowns"), list):
        errors.append("reconstruction project_summary.unknowns must be a list")
    errors.extend(
        _confidence_errors(
            summary.get("confidence"),
            "reconstruction project_summary.confidence",
        )
    )
    return errors


def _reconstruction_asset_errors(
    assets: list[object],
    *,
    mode: str,
    evidence_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    candidate_ids: set[str] = set()
    for index, asset in enumerate(assets):
        item_errors, candidate_id = _reconstruction_asset_item_errors(
            asset,
            index=index,
            mode=mode,
            evidence_refs=evidence_refs,
            candidate_ids=candidate_ids,
        )
        errors.extend(item_errors)
        if candidate_id:
            candidate_ids.add(candidate_id)
    return errors


def _reconstruction_asset_item_errors(
    asset: object,
    *,
    index: int,
    mode: str,
    evidence_refs: set[str],
    candidate_ids: set[str],
) -> tuple[list[str], str]:
    prefix = f"assets[{index}]"
    if not isinstance(asset, dict):
        return [f"{prefix} must be an object"], ""
    asset_type = str(asset.get("asset_type") or "").strip().lower().replace("_", "-")
    candidate_id = str(asset.get("candidate_id") or "")
    errors = _asset_identity_errors(
        asset_type,
        candidate_id,
        prefix=prefix,
        candidate_ids=candidate_ids,
    )
    errors.extend(_asset_recommendation_errors(asset, prefix=prefix, mode=mode))
    errors.extend(_asset_evidence_errors(asset, prefix=prefix, evidence_refs=evidence_refs))
    errors.extend(_asset_payload_errors(asset, prefix, asset_type, candidate_id))
    return errors, candidate_id


def _asset_identity_errors(
    asset_type: str,
    candidate_id: str,
    *,
    prefix: str,
    candidate_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    if asset_type not in ASSET_SCHEMA_NAMES:
        errors.append(f"{prefix}.asset_type is not an Archive candidate type")
    if not _safe_id(candidate_id):
        errors.append(f"{prefix}.candidate_id must be a stable safe id")
    if candidate_id in candidate_ids:
        errors.append(f"duplicate reconstruction candidate_id: {candidate_id}")
    return errors


def _asset_recommendation_errors(
    asset: dict[str, Any],
    *,
    prefix: str,
    mode: str,
) -> list[str]:
    recommendation = str(asset.get("promotion_recommendation") or "")
    errors: list[str] = []
    if recommendation not in PROMOTION_RECOMMENDATIONS:
        errors.append(
            f"{prefix}.promotion_recommendation must be one of "
            f"{sorted(PROMOTION_RECOMMENDATIONS)}"
        )
    if mode == "analysis" and recommendation != "analysis_only":
        errors.append(f"{prefix} must be analysis_only in analysis mode")
    return errors


def _asset_evidence_errors(
    asset: dict[str, Any],
    *,
    prefix: str,
    evidence_refs: set[str],
) -> list[str]:
    refs = _string_list(asset.get("evidence_refs"))
    errors = [] if refs else [f"{prefix}.evidence_refs must be non-empty"]
    unknown = sorted(set(refs) - evidence_refs)
    if unknown:
        errors.append(f"{prefix}.evidence_refs contains unknown refs: {', '.join(unknown)}")
    errors.extend(_confidence_errors(asset.get("confidence"), f"{prefix}.confidence"))
    if not isinstance(asset.get("unresolved_refs"), list):
        errors.append(f"{prefix}.unresolved_refs must be a list")
    return errors


def _asset_payload_errors(
    asset: dict[str, Any],
    prefix: str,
    asset_type: str,
    candidate_id: str,
) -> list[str]:
    payload = asset.get("payload")
    if not isinstance(payload, dict):
        return [f"{prefix}.payload must be an object"]
    if asset_type not in ASSET_SCHEMA_NAMES:
        return []
    return _candidate_payload_errors(
        payload,
        asset_type=asset_type,
        candidate_id=candidate_id,
        prefix=f"{prefix}.payload",
    )


def read_json_object(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"JSON artifact missing: {path.name}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, [f"JSON artifact is invalid: {path.name} ({exc})"]
    if not isinstance(payload, dict):
        return {}, [f"JSON artifact root must be an object: {path.name}"]
    return payload, []


def _identity_errors(payload: dict[str, Any], **expected: str) -> list[str]:
    errors: list[str] = []
    for field, value in expected.items():
        if str(payload.get(field) or "") != value:
            errors.append(f"{field} must be {value or 'non-empty'}")
    if payload.get("revision") != canonical_digest(payload):
        errors.append("revision does not match artifact content")
    return errors


def _conflict_review_errors(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
) -> list[str]:
    conflicts = aggregate.get("conflicts")
    expected = set(range(len(conflicts))) if isinstance(conflicts, list) else set()
    reviews = payload.get("conflict_reviews")
    if not isinstance(reviews, list):
        return ["identity resolution conflict_reviews must be a list"]
    seen: list[int] = []
    errors: list[str] = []
    for index, review in enumerate(reviews):
        prefix = f"conflict_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue
        conflict_index = review.get("conflict_index")
        if not isinstance(conflict_index, int) or isinstance(conflict_index, bool):
            errors.append(f"{prefix}.conflict_index must be an integer")
            continue
        seen.append(conflict_index)
        if conflict_index not in expected:
            errors.append(f"{prefix}.conflict_index is outside the aggregate")
        disposition = str(review.get("disposition") or "")
        if disposition not in CONFLICT_DISPOSITIONS:
            errors.append(
                f"{prefix}.disposition must be one of {sorted(CONFLICT_DISPOSITIONS)}"
            )
        errors.extend(_evidence_judgment_errors(review, prefix))
    if set(seen) != expected or len(seen) != len(set(seen)):
        errors.append("conflict reviews must cover every aggregate conflict exactly once")
    return errors


def _candidate_payload_errors(
    payload: dict[str, Any],
    *,
    asset_type: str,
    candidate_id: str,
    prefix: str,
) -> list[str]:
    errors, _warnings = validate_payload(payload, ASSET_SCHEMA_NAMES[asset_type])
    result = [f"{prefix}.{item['path']}: {item['message']}" for item in errors]
    if str(payload.get("candidate_id") or "") != candidate_id:
        result.append(f"{prefix}.candidate_id must match the reconstruction candidate_id")
    return result


def _domain_observation_errors(
    payload: dict[str, Any],
    evidence_refs: set[str],
) -> list[str]:
    observations = payload.get("domain_observations")
    if not isinstance(observations, list):
        return ["reconstruction domain_observations must be a list"]
    errors: list[str] = []
    for index, item in enumerate(observations):
        prefix = f"domain_observations[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if str(item.get("domain") or "") not in ARCHAEOLOGY_DOMAINS:
            errors.append(f"{prefix}.domain must be one of {list(ARCHAEOLOGY_DOMAINS)}")
        refs = _string_list(item.get("evidence_refs"))
        if not refs:
            errors.append(f"{prefix}.evidence_refs must be non-empty")
        unknown = sorted(set(refs) - evidence_refs)
        if unknown:
            errors.append(f"{prefix}.evidence_refs contains unknown refs: {', '.join(unknown)}")
        errors.extend(_confidence_errors(item.get("confidence"), f"{prefix}.confidence"))
    return errors


def _evidence_judgment_errors(item: dict[str, Any], prefix: str) -> list[str]:
    errors = _confidence_errors(item.get("confidence"), f"{prefix}.confidence")
    if not _string_list(item.get("evidence_refs")):
        errors.append(f"{prefix}.evidence_refs must be non-empty")
    if not str(item.get("rationale") or "").strip():
        errors.append(f"{prefix}.rationale is required")
    if not isinstance(item.get("unknowns"), list):
        errors.append(f"{prefix}.unknowns must be a list")
    return errors


def _confidence_errors(value: object, field: str) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return [f"{field} must be a number between 0 and 1"]
    return [] if 0 <= float(value) <= 1 else [f"{field} must be between 0 and 1"]


def _aggregate_evidence_refs(aggregate: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for collection in (
        "entity_occurrences",
        "event_occurrences",
        "relation_occurrences",
        "claim_occurrences",
        "conflicts",
    ):
        for item in aggregate.get(collection) or []:
            if isinstance(item, dict):
                refs.update(_string_list(item.get("evidence_refs")))
    return refs


def _evidence_revision(manifest: dict[str, Any]) -> str:
    evidence = manifest.get("evidence_index")
    return str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _safe_id(value: str) -> bool:
    return bool(value and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value))
