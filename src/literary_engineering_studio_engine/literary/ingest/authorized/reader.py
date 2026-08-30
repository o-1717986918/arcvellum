"""Read-only projection over exact ranges of an authorized imported source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ....foundation.atomic_io import atomic_write_text


AUTHORIZED_READER_SCHEMA = "arcvellum/authorized-reader-manifest/v1"
DEFAULT_READER_CHUNK_SIZE = 12000


def write_authorized_reader_manifest(
    project_root: Path | str,
    *,
    work_id: str,
    title: str,
    author: str,
    edition: str,
    authorized_manifest_digest: str,
    ingest_manifest_path: Path | str,
    chunk_size: int = DEFAULT_READER_CHUNK_SIZE,
) -> Path:
    root = Path(project_root).resolve()
    ingest_path = _resolve_project_path(root, ingest_manifest_path)
    ingest = _read_json(ingest_path)
    documents = ingest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("source ingest manifest contains no source documents")
    units: list[dict[str, Any]] = []
    for document_index, document in enumerate(documents, 1):
        if not isinstance(document, Mapping):
            continue
        units.extend(
            _document_units(
                root,
                work_id=work_id,
                work_title=title,
                document=document,
                document_index=document_index,
                chunk_size=max(2000, int(chunk_size)),
            )
        )
    if not units:
        raise ValueError("authorized source contains no reader-visible text")
    for index, unit in enumerate(units, 1):
        unit["order"] = index
    output = root / "sources" / "authorized" / work_id / "reader_manifest.json"
    payload = {
        "schema": AUTHORIZED_READER_SCHEMA,
        "work_id": work_id,
        "title": title,
        "author": author,
        "edition": edition,
        "authorized_manifest_digest": authorized_manifest_digest,
        "ingest_manifest": ingest_path.relative_to(root).as_posix(),
        "unit_count": len(units),
        "units": units,
    }
    atomic_write_text(
        output,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return output


def load_authorized_reader_units(project_root: Path | str) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    units: list[dict[str, Any]] = []
    manifests = sorted((root / "sources" / "authorized").glob("*/reader_manifest.json"))
    for manifest_path in manifests:
        payload = _read_json(manifest_path)
        if payload.get("schema") != AUTHORIZED_READER_SCHEMA:
            continue
        work_id = str(payload.get("work_id") or manifest_path.parent.name)
        title = str(payload.get("title") or work_id)
        author = str(payload.get("author") or "")
        for item in payload.get("units", []):
            if not isinstance(item, Mapping):
                continue
            record = dict(item)
            record["authorized_work_id"] = work_id
            record["authorized_work_title"] = title
            record["authorized_author"] = author
            try:
                body = read_authorized_reader_body(root, record)
            except (OSError, ValueError):
                continue
            record["body"] = body
            units.append(record)
    units.sort(key=lambda item: (str(item.get("authorized_work_id") or ""), int(item.get("order") or 0)))
    return units


def read_authorized_reader_body(
    project_root: Path | str,
    unit: Mapping[str, Any],
) -> str:
    root = Path(project_root).resolve()
    source = _resolve_project_path(root, str(unit.get("source_path") or ""))
    text = source.read_text(encoding="utf-8")
    start = _integer(unit.get("char_start"), default=-1)
    end = _integer(unit.get("char_end"), default=-1)
    if start < 0 or end <= start or end > len(text):
        raise ValueError("authorized reader range is outside the imported source")
    body = text[start:end]
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if digest != str(unit.get("content_hash") or ""):
        raise ValueError("authorized reader source range hash mismatch")
    return body


def _document_units(
    root: Path,
    *,
    work_id: str,
    work_title: str,
    document: Mapping[str, Any],
    document_index: int,
    chunk_size: int,
) -> list[dict[str, Any]]:
    source_path = str(document.get("raw_path") or "")
    source = _resolve_project_path(root, source_path)
    text = source.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != str(document.get("extracted_text_hash") or ""):
        raise ValueError("imported source text no longer matches the source ingest manifest")
    sections = _document_sections(text, document, work_title)
    result: list[dict[str, Any]] = []
    for section_start, section_end, section_title in sections:
        ranges = _split_range(text, section_start, section_end, chunk_size)
        for part_index, (start, end) in enumerate(ranges, 1):
            body = text[start:end]
            if not body.strip():
                continue
            result.append(
                _reader_unit_record(
                    work_id=work_id,
                    document_index=document_index,
                    ordinal=len(result) + 1,
                    source_path=source_path,
                    source_id=str(document.get("source_id") or ""),
                    section_title=section_title,
                    part_index=part_index,
                    is_split=section_end - section_start > chunk_size,
                    start=start,
                    end=end,
                    body=body,
                )
            )
    return result


def _document_sections(
    text: str,
    document: Mapping[str, Any],
    work_title: str,
) -> list[tuple[int, int, str]]:
    headings = [
        item
        for item in document.get("bounds", [])
        if isinstance(item, Mapping) and str(item.get("kind") or "") == "heading"
    ]
    boundaries: list[tuple[int, str]] = []
    for heading in headings:
        start = _integer(heading.get("char_start"), default=-1)
        end = _integer(heading.get("char_end"), default=-1)
        if start < 0 or end <= start or end > len(text):
            continue
        boundaries.append((start, text[start:end].strip()))
    boundaries.sort(key=lambda item: item[0])
    if not boundaries:
        return [(0, len(text), work_title)]
    sections: list[tuple[int, int, str]] = []
    if boundaries[0][0] > 0 and text[:boundaries[0][0]].strip():
        sections.append((0, boundaries[0][0], "卷首"))
    for index, (start, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        sections.append((start, end, heading or f"阅读分段 {index + 1}"))
    return sections


def _reader_unit_record(
    *,
    work_id: str,
    document_index: int,
    ordinal: int,
    source_path: str,
    source_id: str,
    section_title: str,
    part_index: int,
    is_split: bool,
    start: int,
    end: int,
    body: str,
) -> dict[str, Any]:
    suffix = f"（{part_index}）" if is_split else ""
    return {
        "unit_id": f"authorized:{work_id}:{document_index:02d}:{ordinal:04d}",
        "chapter_id": f"authorized_section_{document_index:02d}_{ordinal:04d}",
        "scene_id": "",
        "title": f"{section_title}{suffix}",
        "status": "authorized",
        "source_kind": "authorized_source",
        "source_path": source_path,
        "source_id": source_id,
        "char_start": start,
        "char_end": end,
        "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def _split_range(text: str, start: int, end: int, chunk_size: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        target = min(end, cursor + chunk_size)
        if target < end:
            break_at = text.rfind("\n\n", cursor + chunk_size // 2, target)
            if break_at > cursor:
                target = break_at + 2
        ranges.append((cursor, target))
        cursor = target
    return ranges


def _resolve_project_path(root: Path, value: Path | str) -> Path:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("authorized reader source escapes the project root") from error
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _integer(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
