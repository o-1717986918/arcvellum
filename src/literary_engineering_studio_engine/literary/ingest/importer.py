"""Transactional deterministic source preservation for Project Archaeology."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from shutil import rmtree
from typing import Callable, TypeVar

from .contracts import SourceChunk
from .evidence import build_evidence_index
from .readers import read_source_documents
from .segmentation import build_source_chunks, segment_documents


_T = TypeVar("_T")


@dataclass(frozen=True)
class StagedSourceImport:
    title: str
    source_documents: tuple[dict[str, object], ...]
    raw_records: tuple[dict[str, object], ...]
    chunk_records: tuple[dict[str, object], ...]
    evidence_revision: str
    segment_count: int

    @property
    def source_count(self) -> int:
        return len(self.source_documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunk_records)


def stage_source_import(
    *,
    staging_dir: Path,
    logical_import: str,
    work_id: str,
    source: Path | None,
    text: str,
    title: str,
    rights_declaration: str,
    chunk_size: int,
) -> StagedSourceImport:
    raw_dir, original_dir, chunk_dir = _prepare_staging(staging_dir)
    documents = read_source_documents(
        source,
        text=text,
        title=title,
        rights_declaration=rights_declaration,
    )
    source_documents, raw_records = _preserve_documents(
        documents,
        raw_dir=raw_dir,
        original_dir=original_dir,
        logical_import=logical_import,
    )
    segments = segment_documents(documents)
    evidence = build_evidence_index(documents, segments)
    (staging_dir / "evidence_index.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    chunk_records = _write_chunks(
        build_source_chunks(segments, chunk_size=chunk_size),
        chunk_dir=chunk_dir,
        logical_import=logical_import,
        work_id=work_id,
    )
    return StagedSourceImport(
        title=title or documents[0].title,
        source_documents=tuple(source_documents),
        raw_records=tuple(raw_records),
        chunk_records=tuple(chunk_records),
        evidence_revision=str(evidence["revision"]),
        segment_count=len(segments),
    )


def recover_interrupted_import(import_dir: Path) -> None:
    backup_dir = import_dir.with_name(f".{import_dir.name}.backup")
    if backup_dir.exists() and not import_dir.exists():
        backup_dir.replace(import_dir)
        return
    if backup_dir.exists() and import_dir.exists():
        rmtree(backup_dir)


def commit_import(staging_dir: Path, import_dir: Path, *, overwrite: bool) -> None:
    backup_dir = import_dir.with_name(f".{import_dir.name}.backup")
    if import_dir.exists() and not overwrite:
        raise FileExistsError(f"source import already exists: {import_dir}")
    if backup_dir.exists():
        rmtree(backup_dir)
    if import_dir.exists():
        import_dir.replace(backup_dir)
    try:
        staging_dir.replace(import_dir)
    except Exception:
        if not import_dir.exists() and backup_dir.exists():
            backup_dir.replace(import_dir)
        raise
    if backup_dir.exists():
        rmtree(backup_dir)


def prepare_import_location(
    root: Path,
    work_id: str,
    *,
    overwrite: bool,
) -> tuple[Path, Path]:
    imports_dir = root / "sources" / "imports"
    import_dir = imports_dir / work_id
    recover_interrupted_import(import_dir)
    if import_dir.exists() and any(import_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"source import already exists: {import_dir}")
    staging_dir = imports_dir / f".{work_id}.importing"
    if staging_dir.exists():
        rmtree(staging_dir)
    return import_dir, staging_dir


def run_import_transaction(
    *,
    staging_dir: Path,
    import_dir: Path,
    overwrite: bool,
    stage: Callable[[], _T],
) -> _T:
    try:
        artifacts = stage()
        commit_import(staging_dir, import_dir, overwrite=overwrite)
        return artifacts
    except Exception:
        if staging_dir.exists():
            rmtree(staging_dir)
        raise


def _prepare_staging(staging_dir: Path) -> tuple[Path, Path, Path]:
    raw_dir = staging_dir / "raw"
    original_dir = staging_dir / "original"
    chunk_dir = staging_dir / "chunks"
    for path in (raw_dir, original_dir, chunk_dir, staging_dir / "extracted"):
        path.mkdir(parents=True, exist_ok=True)
    return raw_dir, original_dir, chunk_dir


def _preserve_documents(
    documents,
    *,
    raw_dir: Path,
    original_dir: Path,
    logical_import: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    manifest_records: list[dict[str, object]] = []
    raw_records: list[dict[str, object]] = []
    for index, document in enumerate(documents, start=1):
        source_stem = Path(document.original_filename).stem or document.title
        stem = f"{index:03d}-{_safe_filename(source_stem)}"
        suffix = Path(document.original_filename).suffix.lower() or ".txt"
        original_name = f"{stem}{suffix}"
        raw_name = f"{stem}.txt"
        (original_dir / original_name).write_bytes(document.original_bytes)
        (raw_dir / raw_name).write_text(document.text, encoding="utf-8")
        logical_original = f"{logical_import}/original/{original_name}"
        logical_raw = f"{logical_import}/raw/{raw_name}"
        manifest_records.append(
            document.manifest_record(
                original_path=logical_original,
                raw_path=logical_raw,
            )
        )
        raw_records.append(
            {
                "source_id": document.source_id,
                "label": document.title,
                "raw_path": logical_raw,
                "char_count": len(document.text),
                "content_sha256": document.extracted_text_hash,
            }
        )
    return manifest_records, raw_records


def _write_chunks(
    chunks: list[SourceChunk],
    *,
    chunk_dir: Path,
    logical_import: str,
    work_id: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for chunk in chunks:
        (chunk_dir / f"{chunk.chunk_id}.md").write_text(
            _render_chunk(work_id, chunk),
            encoding="utf-8",
        )
        records.append(
            chunk.to_record(
                path=f"{logical_import}/chunks/{chunk.chunk_id}.md",
            )
        )
    return records


def _render_chunk(work_id: str, chunk: SourceChunk) -> str:
    heading_paths = [" / ".join(path) for path in chunk.heading_paths if path]
    return "\n".join(
        [
            f"# Source Chunk {chunk.chunk_id}",
            "",
            f"- work_id: `{work_id}`",
            f"- chunk_id: `{chunk.chunk_id}`",
            f"- source_id: `{chunk.source_id}`",
            f"- segment_ids: {json.dumps(list(chunk.segment_ids), ensure_ascii=False)}",
            f"- evidence_refs: {json.dumps(list(chunk.evidence_ids), ensure_ascii=False)}",
            f"- heading_paths: {json.dumps(heading_paths, ensure_ascii=False)}",
            f"- char_start: {chunk.char_start}",
            f"- char_end: {chunk.char_end}",
            f"- paragraph_start: {chunk.paragraph_start}",
            f"- paragraph_end: {chunk.paragraph_end}",
            "",
            "## Text",
            "",
            chunk.text.strip(),
            "",
        ]
    )


def _safe_filename(value: object) -> str:
    from .readers.common import slug

    return slug(str(value))[:60] or "source"
