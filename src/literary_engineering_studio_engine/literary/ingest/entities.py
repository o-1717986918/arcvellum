"""Evidence-bound contracts for chunk-level archaeology extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CHUNK_EXTRACTION_SCHEMA = "arcvellum/project-archaeology-chunk-extraction/v1"
ENTITY_TYPES = {
    "character",
    "location",
    "organization",
    "object",
    "concept",
    "collective",
    "unknown",
}
CONFIDENCE_FIELDS = ("confidence",)
EXTRACTION_COLLECTIONS = ("entities", "events", "relations", "claims")


def chunk_extraction_path(import_dir: str | Path, chunk_id: str) -> str:
    base = Path(import_dir).as_posix().rstrip("/")
    return f"{base}/extractions/chunks/{_safe_id(chunk_id)}.json"


def chunk_file_sha256(root: Path, chunk: dict[str, Any]) -> str:
    path = _project_path(root, chunk.get("path"))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def validate_chunk_extraction(
    payload: dict[str, Any],
    *,
    work_id: str,
    chunk: dict[str, Any],
    evidence_revision: str,
    root: Path | None = None,
) -> list[str]:
    """Validate one Agent extraction against the exact immutable source chunk."""

    expected_refs = {
        str(item)
        for item in chunk.get("evidence_refs", [])
        if str(item).strip()
    }
    errors = _chunk_identity_errors(
        payload,
        work_id=work_id,
        chunk=chunk,
        evidence_revision=evidence_revision,
        root=root,
    )
    entity_ids, event_ids, inventory_errors = _candidate_inventory(
        payload,
        expected_evidence_refs=expected_refs,
    )
    errors.extend(inventory_errors)
    errors.extend(
        _relation_reference_errors(
            payload.get("relations"),
            entity_ids=entity_ids,
        )
    )
    errors.extend(
        _claim_reference_errors(
            payload.get("claims"),
            subject_ids=entity_ids | event_ids,
        )
    )
    from .timeline import validate_event_candidates

    errors.extend(
        validate_event_candidates(
            payload.get("events"),
            candidate_ids=entity_ids,
            expected_evidence_refs=expected_refs,
        )
    )
    return errors


def _chunk_identity_errors(
    payload: dict[str, Any],
    *,
    work_id: str,
    chunk: dict[str, Any],
    evidence_revision: str,
    root: Path | None,
) -> list[str]:
    expected = {
        "schema": CHUNK_EXTRACTION_SCHEMA,
        "work_id": work_id,
        "chunk_id": str(chunk.get("chunk_id") or ""),
        "source_chunk_path": str(chunk.get("path") or "").replace("\\", "/"),
        "evidence_revision": evidence_revision,
        "status": "complete",
    }
    errors: list[str] = []
    for field, value in expected.items():
        actual = str(payload.get(field) or "").replace("\\", "/")
        if actual != value:
            errors.append(
                f"chunk extraction {field} must be {value or 'non-empty'}; "
                f"got {actual or 'missing'}"
            )
    if root is not None:
        expected_hash = chunk_file_sha256(root, chunk)
        actual_hash = str(payload.get("source_chunk_sha256") or "").lower()
        if not expected_hash or actual_hash != expected_hash:
            errors.append("chunk extraction source_chunk_sha256 does not match source chunk")
    return errors


def _candidate_inventory(
    payload: dict[str, Any],
    *,
    expected_evidence_refs: set[str],
) -> tuple[set[str], set[str], list[str]]:
    records: set[str] = set()
    entity_ids: set[str] = set()
    event_ids: set[str] = set()
    errors: list[str] = []
    for collection in EXTRACTION_COLLECTIONS:
        values = payload.get(collection)
        if not isinstance(values, list):
            errors.append(f"chunk extraction {collection} must be a list")
            continue
        for index, item in enumerate(values):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            candidate_id = str(item.get("candidate_id") or "").strip()
            errors.extend(_candidate_id_errors(candidate_id, records, prefix))
            if candidate_id and candidate_id not in records:
                records.add(candidate_id)
                if collection == "entities":
                    entity_ids.add(candidate_id)
                elif collection == "events":
                    event_ids.add(candidate_id)
            errors.extend(
                _common_candidate_errors(
                    item,
                    prefix=prefix,
                    expected_evidence_refs=expected_evidence_refs,
                )
            )
            if collection == "entities":
                errors.extend(
                    _entity_errors(
                        item,
                        prefix=prefix,
                        expected_evidence_refs=expected_evidence_refs,
                    )
                )
    return entity_ids, event_ids, errors


def _candidate_id_errors(
    candidate_id: str,
    records: set[str],
    prefix: str,
) -> list[str]:
    if not candidate_id:
        return [f"{prefix}.candidate_id is required"]
    if candidate_id in records:
        return [f"duplicate chunk candidate_id: {candidate_id}"]
    return []


def read_chunk_extraction(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"chunk extraction missing: {path.name}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, [f"chunk extraction is not valid UTF-8 JSON: {path.name} ({exc})"]
    if not isinstance(payload, dict):
        return {}, [f"chunk extraction root must be an object: {path.name}"]
    return payload, []


def _common_candidate_errors(
    item: dict[str, Any],
    *,
    prefix: str,
    expected_evidence_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    refs = item.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{prefix}.evidence_refs must be a non-empty list")
    else:
        normalized = [str(value) for value in refs if str(value).strip()]
        unknown = sorted(set(normalized) - expected_evidence_refs)
        if unknown:
            errors.append(
                f"{prefix}.evidence_refs contains evidence outside the source chunk: "
                + ", ".join(unknown)
            )
    for field in CONFIDENCE_FIELDS:
        value = item.get(field)
        if isinstance(value, bool) or not isinstance(value, int | float):
            errors.append(f"{prefix}.{field} must be a number from 0 to 1")
        elif not 0 <= float(value) <= 1:
            errors.append(f"{prefix}.{field} must be between 0 and 1")
    for field in ("unknowns", "contradiction_notes"):
        if not isinstance(item.get(field), list):
            errors.append(f"{prefix}.{field} must be a list")
    return errors


def _entity_errors(
    item: dict[str, Any],
    *,
    prefix: str,
    expected_evidence_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    entity_type = str(item.get("entity_type") or "").strip().lower()
    if entity_type not in ENTITY_TYPES:
        errors.append(
            f"{prefix}.entity_type must be one of {', '.join(sorted(ENTITY_TYPES))}"
        )
    if not str(item.get("name") or "").strip():
        errors.append(f"{prefix}.name is required")
    aliases = item.get("aliases")
    if not isinstance(aliases, list):
        errors.append(f"{prefix}.aliases must be a list")
    attributes = item.get("attributes")
    if not isinstance(attributes, list):
        errors.append(f"{prefix}.attributes must be a list")
    else:
        for index, attribute in enumerate(attributes):
            if not isinstance(attribute, dict):
                errors.append(f"{prefix}.attributes[{index}] must be an object")
                continue
            if not str(attribute.get("key") or "").strip():
                errors.append(f"{prefix}.attributes[{index}].key is required")
            if "value" not in attribute:
                errors.append(f"{prefix}.attributes[{index}].value is required")
            errors.extend(
                _bounded_evidence_errors(
                    attribute,
                    prefix=f"{prefix}.attributes[{index}]",
                    expected_evidence_refs=expected_evidence_refs,
                )
            )
    return errors


def _relation_reference_errors(
    relations: Any,
    *,
    entity_ids: set[str],
) -> list[str]:
    if not isinstance(relations, list):
        return []
    errors: list[str] = []
    for index, item in enumerate(relations):
        if not isinstance(item, dict):
            continue
        if not str(item.get("relation_type") or "").strip():
            errors.append(f"relations[{index}].relation_type is required")
        for field in ("source_entity_id", "target_entity_id"):
            value = str(item.get(field) or "").strip()
            if not value:
                errors.append(f"relations[{index}].{field} is required")
            elif value not in entity_ids:
                errors.append(
                    f"relations[{index}].{field} references unknown entity: {value}"
                )
    return errors


def _claim_reference_errors(
    claims: Any,
    *,
    subject_ids: set[str],
) -> list[str]:
    if not isinstance(claims, list):
        return []
    errors: list[str] = []
    for index, item in enumerate(claims):
        if not isinstance(item, dict):
            continue
        for field in ("domain", "predicate"):
            if not str(item.get(field) or "").strip():
                errors.append(f"claims[{index}].{field} is required")
        subject = str(item.get("subject_ref") or "").strip()
        if not subject:
            errors.append(f"claims[{index}].subject_ref is required")
        elif subject not in subject_ids:
            errors.append(
                f"claims[{index}].subject_ref references unknown entity or event: {subject}"
            )
        if "value" not in item:
            errors.append(f"claims[{index}].value is required")
    return errors


def _bounded_evidence_errors(
    item: dict[str, Any],
    *,
    prefix: str,
    expected_evidence_refs: set[str],
) -> list[str]:
    errors: list[str] = []
    refs = item.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{prefix}.evidence_refs must be a non-empty list")
    else:
        unknown = sorted(set(str(value) for value in refs) - expected_evidence_refs)
        if unknown:
            errors.append(
                f"{prefix}.evidence_refs contains evidence outside the source chunk: "
                + ", ".join(unknown)
            )
    confidence = item.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0 <= float(confidence) <= 1
    ):
        errors.append(f"{prefix}.confidence must be a number from 0 to 1")
    return errors


def _project_path(root: Path, value: Any) -> Path:
    relative = Path(str(value or "").replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        return root / "__invalid_source_path__"
    return root / relative


def _safe_id(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in value.strip()
    ).strip("-_")
    return cleaned or "chunk"
