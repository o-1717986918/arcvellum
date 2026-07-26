"""Deterministic fan-in for evidence-bound archaeology chunk extractions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .aliases import build_alias_groups
from .conflicts import discover_extraction_conflicts
from .entities import (
    EXTRACTION_COLLECTIONS,
    chunk_extraction_path,
    read_chunk_extraction,
    validate_chunk_extraction,
)
from .evidence import canonical_digest


ARCHAEOLOGY_AGGREGATE_SCHEMA = "arcvellum/project-archaeology-aggregate/v1"
ARCHAEOLOGY_PLAN_SCHEMA = "arcvellum/project-archaeology-extraction-plan/v1"


def build_chunk_extraction_plan(
    manifest: dict[str, Any],
    *,
    import_dir: str | Path,
) -> list[dict[str, Any]]:
    work_id = str(manifest.get("work_id") or Path(import_dir).name)
    evidence = manifest.get("evidence_index")
    evidence_revision = (
        str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""
    )
    plan: list[dict[str, Any]] = []
    for chunk in manifest.get("chunks") or []:
        if not isinstance(chunk, dict):
            continue
        chunk_id = str(chunk.get("chunk_id") or "")
        plan.append(
            {
                "work_id": work_id,
                "chunk_id": chunk_id,
                "source_chunk_path": str(chunk.get("path") or ""),
                "source_evidence_refs": [
                    str(item) for item in chunk.get("evidence_refs") or []
                ],
                "evidence_revision": evidence_revision,
                "expected_output": chunk_extraction_path(import_dir, chunk_id),
                "task_path": _chunk_task_path(import_dir, chunk_id),
                "completion_path": _chunk_completion_path(import_dir, chunk_id),
            }
        )
    return plan


def build_archaeology_plan(
    manifest: dict[str, Any],
    *,
    import_dir: str | Path,
) -> dict[str, Any]:
    base = Path(import_dir).as_posix().rstrip("/")
    return {
        "schema": ARCHAEOLOGY_PLAN_SCHEMA,
        "chunk_tasks": build_chunk_extraction_plan(
            manifest,
            import_dir=import_dir,
        ),
        "aggregate_path": f"{base}/extractions/aggregate.json",
    }


def verify_archaeology_plan(
    manifest: dict[str, Any],
    *,
    import_dir: str | Path,
) -> list[str]:
    plan = manifest.get("archaeology")
    if plan is None:
        return []
    if not isinstance(plan, dict):
        return ["source manifest archaeology plan must be an object"]
    errors: list[str] = []
    if plan.get("schema") != ARCHAEOLOGY_PLAN_SCHEMA:
        errors.append("source manifest archaeology plan has wrong schema")
    expected = build_archaeology_plan(manifest, import_dir=import_dir)
    if plan != expected:
        errors.append("source manifest archaeology plan does not match source chunks")
    return errors


def aggregate_chunk_extractions(
    root: Path,
    manifest: dict[str, Any],
    *,
    import_dir: str | Path,
) -> tuple[dict[str, Any], list[str]]:
    """Build an aggregate even when blocked, so missing work remains observable."""

    work_id = str(manifest.get("work_id") or Path(import_dir).name)
    evidence = manifest.get("evidence_index")
    evidence_revision = (
        str(evidence.get("revision") or "") if isinstance(evidence, dict) else ""
    )
    import_revision = str(manifest.get("import_revision") or "")
    expected_plan = build_chunk_extraction_plan(manifest, import_dir=import_dir)
    chunks_by_id = {
        str(item.get("chunk_id") or ""): item
        for item in manifest.get("chunks") or []
        if isinstance(item, dict)
    }
    accepted, received_ids, errors = _load_valid_extractions(
        root,
        expected_plan=expected_plan,
        chunks_by_id=chunks_by_id,
        work_id=work_id,
        evidence_revision=evidence_revision,
    )
    occurrences = {
        collection: _namespace_occurrences(accepted, collection)
        for collection in EXTRACTION_COLLECTIONS
    }
    alias_groups = build_alias_groups(occurrences["entities"])
    conflicts = discover_extraction_conflicts(
        entity_occurrences=occurrences["entities"],
        claim_occurrences=occurrences["claims"],
        event_occurrences=occurrences["events"],
        relation_occurrences=occurrences["relations"],
        alias_groups=alias_groups,
    )
    expected_ids = [str(item["chunk_id"]) for item in expected_plan]
    missing_ids = [item for item in expected_ids if item not in received_ids]
    fan_in_status = "ready" if not errors and not missing_ids else "blocked"
    payload: dict[str, Any] = {
        "schema": ARCHAEOLOGY_AGGREGATE_SCHEMA,
        "work_id": work_id,
        "import_revision": import_revision,
        "evidence_revision": evidence_revision,
        "fan_in": {
            "status": fan_in_status,
            "expected_chunk_ids": expected_ids,
            "received_chunk_ids": received_ids,
            "missing_chunk_ids": missing_ids,
            "invalid_count": len(errors),
            "errors": errors,
        },
        "entity_occurrences": occurrences["entities"],
        "event_occurrences": occurrences["events"],
        "relation_occurrences": occurrences["relations"],
        "claim_occurrences": occurrences["claims"],
        "alias_groups": alias_groups,
        "conflicts": conflicts,
        "rules": [
            "Occurrences are provisional evidence, not confirmed project facts.",
            "Lexical alias groups never merge identities automatically.",
            "Conflicting alternatives remain unresolved until Agent review.",
            "Formal reconstruction and Archive promotion require a ready fan-in.",
        ],
    }
    payload["revision"] = canonical_digest(payload)
    return payload, errors


def _load_valid_extractions(
    root: Path,
    *,
    expected_plan: list[dict[str, Any]],
    chunks_by_id: dict[str, dict[str, Any]],
    work_id: str,
    evidence_revision: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    accepted: list[dict[str, Any]] = []
    received_ids: list[str] = []
    errors: list[str] = []
    for item in expected_plan:
        chunk_id = str(item["chunk_id"])
        relative = str(item["expected_output"])
        payload, read_errors = read_chunk_extraction(root / relative)
        if read_errors:
            errors.extend(f"{relative}: {message}" for message in read_errors)
            continue
        validation_errors = validate_chunk_extraction(
            payload,
            work_id=work_id,
            chunk=chunks_by_id[chunk_id],
            evidence_revision=evidence_revision,
            root=root,
        )
        if validation_errors:
            errors.extend(f"{relative}: {message}" for message in validation_errors)
            continue
        accepted.append(payload)
        received_ids.append(chunk_id)
    return accepted, received_ids, errors


def verify_archaeology_aggregate(
    root: Path,
    manifest: dict[str, Any],
    aggregate: dict[str, Any],
    *,
    import_dir: str | Path,
) -> list[str]:
    expected, errors = aggregate_chunk_extractions(
        root,
        manifest,
        import_dir=import_dir,
    )
    if aggregate.get("schema") != ARCHAEOLOGY_AGGREGATE_SCHEMA:
        errors.append("archaeology aggregate has wrong schema")
    if str(aggregate.get("revision") or "") != canonical_digest(aggregate):
        errors.append("archaeology aggregate revision does not match its content")
    if aggregate != expected:
        errors.append(
            "archaeology aggregate does not match current source chunk extractions"
        )
    if (aggregate.get("fan_in") or {}).get("status") != "ready":
        errors.append("archaeology aggregate fan-in is not ready")
    return list(dict.fromkeys(errors))


def write_archaeology_aggregate(
    root: Path,
    manifest: dict[str, Any],
    *,
    import_dir: str | Path,
    output: Path,
) -> tuple[Path, list[str]]:
    payload, errors = aggregate_chunk_extractions(
        root,
        manifest,
        import_dir=import_dir,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output, errors


def aggregate_source_import(
    project_root: Path,
    work_id: str,
) -> tuple[Path, list[str]]:
    root = project_root.resolve()
    safe_work_id = _validated_work_id(work_id)
    import_dir = (root / "sources" / "imports" / safe_work_id).resolve()
    imports_root = (root / "sources" / "imports").resolve()
    if not import_dir.is_relative_to(imports_root):
        raise ValueError("source import path leaves the work project")
    manifest_path = import_dir / "source_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"source manifest not found for work_id: {safe_work_id}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"source manifest is not valid UTF-8 JSON: {safe_work_id}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("source manifest root must be an object")
    plan = manifest.get("archaeology")
    if not isinstance(plan, dict):
        raise ValueError("source import does not contain an archaeology extraction plan")
    output = _project_output_path(
        root,
        plan.get("aggregate_path"),
        import_dir=import_dir,
    )
    return write_archaeology_aggregate(
        root,
        manifest,
        import_dir=import_dir.relative_to(root),
        output=output,
    )


def _namespace_occurrences(
    payloads: list[dict[str, Any]],
    collection: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for payload in sorted(payloads, key=lambda item: str(item.get("chunk_id") or "")):
        chunk_id = str(payload.get("chunk_id") or "")
        records = payload.get(collection)
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            candidate_id = str(record.get("candidate_id") or "")
            namespaced = _namespace_references(record, chunk_id)
            result.append(
                {
                    **namespaced,
                    "candidate_ref": f"{chunk_id}::{candidate_id}",
                    "chunk_id": chunk_id,
                }
            )
    return result


def _namespace_references(record: dict[str, Any], chunk_id: str) -> dict[str, Any]:
    result = dict(record)
    for field in ("source_entity_id", "target_entity_id", "subject_ref"):
        value = str(result.get(field) or "")
        if value:
            result[field] = f"{chunk_id}::{value}"
    if isinstance(result.get("participant_refs"), list):
        result["participant_refs"] = [
            f"{chunk_id}::{value}" for value in result["participant_refs"]
        ]
    return result


def _chunk_task_path(import_dir: str | Path, chunk_id: str) -> str:
    base = Path(import_dir).as_posix().rstrip("/")
    stem = Path(chunk_extraction_path(import_dir, chunk_id)).stem
    return f"{base}/extractions/tasks/{stem}.agent_tasks.md"


def _chunk_completion_path(import_dir: str | Path, chunk_id: str) -> str:
    task_path = _chunk_task_path(import_dir, chunk_id)
    return task_path[: -len(".agent_tasks.md")] + ".agent_completion.json"


def _validated_work_id(value: str) -> str:
    work_id = value.strip()
    if (
        not work_id
        or "/" in work_id
        or "\\" in work_id
        or work_id in {".", ".."}
    ):
        raise ValueError("work_id must be a single source-import directory name")
    return work_id


def _project_output_path(
    root: Path,
    value: object,
    *,
    import_dir: Path,
) -> Path:
    relative = Path(str(value or "").replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("archaeology aggregate path must be project-relative")
    output = (root / relative).resolve()
    if not output.is_relative_to(import_dir):
        raise ValueError("archaeology aggregate path must stay inside the source import")
    return output
