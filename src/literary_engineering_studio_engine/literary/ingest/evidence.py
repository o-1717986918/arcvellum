"""Evidence index construction and deterministic source-manifest validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import (
    EXTRACTOR_VERSION,
    SOURCE_INGEST_SCHEMA_V2,
    SourceDocument,
    SourceEvidenceRef,
    SourceSegment,
)


def build_evidence_index(
    documents: list[SourceDocument],
    segments: list[SourceSegment],
) -> dict[str, Any]:
    evidence = [
        SourceEvidenceRef(
            evidence_id=f"evidence:{segment.segment_id}",
            source_id=segment.source_id,
            segment_id=segment.segment_id,
            range_id=segment.range_id,
            char_start=segment.char_start,
            char_end=segment.char_end,
            paragraph_start=segment.paragraph_start,
            paragraph_end=segment.paragraph_end,
            page_start=segment.page_start,
            page_end=segment.page_end,
            content_hash=segment.content_hash,
            extractor_version=EXTRACTOR_VERSION,
        )
        for segment in segments
    ]
    payload: dict[str, Any] = {
        "schema": "arcvellum/project-archaeology-evidence-index/v1",
        "extractor_version": EXTRACTOR_VERSION,
        "source_count": len(documents),
        "segment_count": len(segments),
        "evidence_count": len(evidence),
        "sources": [
            {
                "source_id": document.source_id,
                "title": document.title,
                "content_hash": document.content_hash,
                "extracted_text_hash": document.extracted_text_hash,
                "bound_count": len(document.bounds),
            }
            for document in documents
        ],
        "segments": [segment.to_record() for segment in segments],
        "evidence": [item.to_record() for item in evidence],
    }
    payload["revision"] = canonical_digest(payload)
    return payload


def canonical_digest(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "revision"}
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def import_revision(manifest: dict[str, Any]) -> str:
    documents = manifest.get("source_documents")
    chunks = manifest.get("chunks")
    evidence = manifest.get("evidence_index")
    return canonical_digest(
        {
            "work_id": manifest.get("work_id"),
            "mode": manifest.get("mode"),
            "sources": [
                {
                    "source_id": record.get("source_id"),
                    "content_hash": record.get("content_hash"),
                    "extracted_text_hash": record.get("extracted_text_hash"),
                }
                for record in documents
                if isinstance(record, dict)
            ]
            if isinstance(documents, list)
            else [],
            "evidence_revision": evidence.get("revision")
            if isinstance(evidence, dict)
            else "",
            "chunk_segment_ids": [
                record.get("segment_ids")
                for record in chunks
                if isinstance(record, dict)
            ]
            if isinstance(chunks, list)
            else [],
        }
    )


def verify_ingest_manifest(root: Path, manifest: dict[str, Any]) -> list[str]:
    if manifest.get("schema") != SOURCE_INGEST_SCHEMA_V2:
        return []
    errors: list[str] = []
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        return ["source_manifest v2 must contain source_documents"]
    evidence_record = manifest.get("evidence_index")
    if not isinstance(evidence_record, dict):
        return ["source_manifest v2 must contain evidence_index"]

    source_ids, document_errors = _verify_documents(root, documents)
    errors.extend(document_errors)
    errors.extend(
        _verify_evidence_record(
            root,
            evidence_record,
            source_ids=source_ids,
            source_ranges=_source_range_map(documents),
            chunks=manifest.get("chunks"),
            expected_segments=int(manifest.get("segment_count") or -1),
        )
    )
    if str(manifest.get("import_revision") or "") != import_revision(manifest):
        errors.append("source manifest import_revision does not match its source graph")
    return errors


def _verify_documents(
    root: Path,
    documents: list[Any],
) -> tuple[set[str], list[str]]:
    source_ids: set[str] = set()
    errors: list[str] = []
    required = (
        "source_id", "media_type", "content_hash", "rights_declaration",
        "extraction_method", "extractor_version", "original_path", "raw_path",
        "extracted_text_hash", "bounds",
    )
    for record in documents:
        if not isinstance(record, dict):
            errors.append("source document record must be an object")
            continue
        errors.extend(
            f"source document is missing {field}"
            for field in required
            if field not in record
        )
        source_id = str(record.get("source_id") or "")
        if source_id in source_ids:
            errors.append(f"duplicate source_id: {source_id}")
        if source_id:
            source_ids.add(source_id)
        errors.extend(_verify_document_files(root, record))
    return source_ids, errors


def _verify_document_files(root: Path, record: dict[str, Any]) -> list[str]:
    source_id = str(record.get("source_id") or "source")
    return [
        *_verify_digest_path(
            root,
            record.get("original_path"),
            record.get("content_hash"),
            f"{source_id} original",
            binary=True,
        ),
        *_verify_digest_path(
            root,
            record.get("raw_path"),
            record.get("extracted_text_hash"),
            f"{source_id} extracted text",
            binary=False,
        ),
    ]


def _verify_evidence_record(
    root: Path,
    record: dict[str, Any],
    *,
    source_ids: set[str],
    source_ranges: dict[tuple[str, str], dict[str, Any]],
    chunks: Any,
    expected_segments: int,
) -> list[str]:
    payload, errors = _read_project_json(root, record.get("path"), "evidence index")
    if not payload:
        return errors
    if payload.get("schema") != "arcvellum/project-archaeology-evidence-index/v1":
        errors.append("evidence index has wrong schema")
    if canonical_digest(payload) != str(payload.get("revision") or ""):
        errors.append("evidence index revision does not match its content")
    if str(payload.get("revision") or "") != str(record.get("revision") or ""):
        errors.append("source manifest evidence revision does not match evidence index")
    errors.extend(
        _verify_evidence_graph(
            payload,
            source_ids,
            source_ranges,
            chunks,
            root,
        )
    )
    if expected_segments != len(payload.get("segments") or []):
        errors.append("source manifest segment_count does not match evidence index")
    return errors


def _verify_evidence_graph(
    payload: dict[str, Any],
    source_ids: set[str],
    source_ranges: dict[tuple[str, str], dict[str, Any]],
    chunks: Any,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    segments = payload.get("segments")
    evidence = payload.get("evidence")
    if not isinstance(segments, list) or not isinstance(evidence, list):
        return ["evidence index must contain segment and evidence lists"]
    segment_map = _records_by_id(segments, "segment_id", "segment", errors)
    evidence_map = _records_by_id(evidence, "evidence_id", "evidence", errors)
    errors.extend(
        _verify_segment_sources(
            segment_map,
            source_ids,
            source_ranges,
        )
    )
    errors.extend(_verify_evidence_links(evidence_map, segment_map))
    if int(payload.get("segment_count") or -1) != len(segment_map):
        errors.append("evidence index segment_count is incorrect")
    if int(payload.get("evidence_count") or -1) != len(evidence_map):
        errors.append("evidence index evidence_count is incorrect")
    errors.extend(_verify_chunks(root, chunks, segment_map, evidence_map))
    return errors


def _verify_segment_sources(
    segments: dict[str, dict[str, Any]],
    source_ids: set[str],
    source_ranges: dict[tuple[str, str], dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for segment_id, record in segments.items():
        source_id = str(record.get("source_id") or "")
        if source_id not in source_ids:
            errors.append(f"segment references unknown source: {segment_id}")
            continue
        source_range = source_ranges.get(
            (source_id, str(record.get("range_id") or ""))
        )
        if not source_range:
            errors.append(f"segment references unknown source range: {segment_id}")
            continue
        mismatches = [
            field
            for field in ("char_start", "char_end", "content_hash")
            if str(record.get(field)) != str(source_range.get(field))
        ]
        errors.extend(
            f"segment {segment_id} does not match source range {field}"
            for field in mismatches
        )
    return errors


def _source_range_map(
    documents: list[Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        source_id = str(document.get("source_id") or "")
        bounds = document.get("bounds")
        if not isinstance(bounds, list):
            continue
        for bound in bounds:
            if isinstance(bound, dict) and str(bound.get("range_id") or ""):
                result[(source_id, str(bound["range_id"]))] = bound
    return result


def _verify_evidence_links(
    evidence: dict[str, dict[str, Any]],
    segments: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for evidence_id, record in evidence.items():
        segment = segments.get(str(record.get("segment_id") or ""))
        if not segment:
            errors.append(f"evidence references unknown segment: {evidence_id}")
            continue
        mismatches = [
            field
            for field in ("source_id", "range_id", "content_hash")
            if str(record.get(field) or "") != str(segment.get(field) or "")
        ]
        errors.extend(
            f"evidence {evidence_id} does not match segment {field}"
            for field in mismatches
        )
    return errors


def _verify_chunks(
    root: Path,
    chunks: Any,
    segments: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(chunks, list) or not chunks:
        return ["source manifest must contain source chunks"]
    errors: list[str] = []
    for record in chunks:
        if not isinstance(record, dict):
            errors.append("source chunk record must be an object")
            continue
        chunk_id = str(record.get("chunk_id") or "chunk")
        chunk_path, path_error = _project_path(root, record.get("path"))
        if path_error:
            errors.append(f"{chunk_id}: {path_error}")
        elif not chunk_path.is_file():
            errors.append(f"{chunk_id} artifact is missing")
        for segment_id in record.get("segment_ids") or []:
            if str(segment_id) not in segments:
                errors.append(f"{chunk_id} references unknown segment: {segment_id}")
        for evidence_id in record.get("evidence_refs") or []:
            if str(evidence_id) not in evidence:
                errors.append(f"{chunk_id} references unknown evidence: {evidence_id}")
    return errors


def _records_by_id(
    records: list[Any],
    field: str,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not str(record.get(field) or ""):
            errors.append(f"{label} record is missing {field}")
            continue
        identifier = str(record[field])
        if identifier in result:
            errors.append(f"duplicate {field}: {identifier}")
        result[identifier] = record
    return result


def _verify_digest_path(
    root: Path,
    relative: Any,
    expected: Any,
    label: str,
    *,
    binary: bool,
) -> list[str]:
    path, error = _project_path(root, relative)
    if error:
        return [f"{label}: {error}"]
    if not path.is_file():
        return [f"{label} is missing"]
    try:
        content = path.read_bytes() if binary else path.read_text(encoding="utf-8").encode("utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{label} cannot be read: {exc}"]
    digest = hashlib.sha256(content).hexdigest()
    return [] if digest == str(expected or "") else [f"{label} hash mismatch"]


def _read_project_json(root: Path, relative: Any, label: str) -> tuple[dict[str, Any], list[str]]:
    path, error = _project_path(root, relative)
    if error:
        return {}, [f"{label}: {error}"]
    if not path.is_file():
        return {}, [f"{label} is missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"{label} is invalid: {exc}"]
    return (payload, []) if isinstance(payload, dict) else ({}, [f"{label} root must be an object"])


def _project_path(root: Path, relative: Any) -> tuple[Path, str]:
    value = str(relative or "").replace("\\", "/").strip()
    if not value or value.startswith("/") or ":" in value.split("/")[0]:
        return root, "path must be project-relative"
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return root, "path escapes the work project"
    return path, ""
