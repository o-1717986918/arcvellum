"""Immutable contracts for Project Archaeology source evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SOURCE_INGEST_SCHEMA_V2 = "literary-engineering-workbench/source-ingest/v2"
EXTRACTOR_VERSION = "arcvellum-ingest/1"


@dataclass(frozen=True)
class SourceRange:
    range_id: str
    kind: str
    ordinal: int
    char_start: int
    char_end: int
    paragraph_start: int
    paragraph_end: int
    content_hash: str
    source_part: str = "document"
    style_name: str = ""
    heading_level: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    footnote_id: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "range_id": self.range_id,
            "kind": self.kind,
            "ordinal": self.ordinal,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
            "content_hash": self.content_hash,
            "source_part": self.source_part,
            "style_name": self.style_name,
            "heading_level": self.heading_level,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "footnote_id": self.footnote_id,
        }


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    title: str
    media_type: str
    content_hash: str
    rights_declaration: str
    extraction_method: str
    bounds: tuple[SourceRange, ...]
    text: str = field(repr=False)
    extracted_text_hash: str = ""
    extractor_version: str = EXTRACTOR_VERSION
    encoding: str = ""
    original_filename: str = ""
    original_bytes: bytes = field(default=b"", repr=False, compare=False)

    def manifest_record(
        self,
        *,
        original_path: str,
        raw_path: str,
    ) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "media_type": self.media_type,
            "content_hash": self.content_hash,
            "rights_declaration": self.rights_declaration,
            "extraction_method": self.extraction_method,
            "extractor_version": self.extractor_version,
            "encoding": self.encoding,
            "original_filename": self.original_filename,
            "original_path": original_path,
            "raw_path": raw_path,
            "extracted_text_hash": self.extracted_text_hash,
            "character_count": len(self.text),
            "bound_count": len(self.bounds),
            "bounds": [item.to_record() for item in self.bounds],
        }


@dataclass(frozen=True)
class SourceSegment:
    segment_id: str
    source_id: str
    range_id: str
    kind: str
    text: str = field(repr=False)
    char_start: int = 0
    char_end: int = 0
    paragraph_start: int = 0
    paragraph_end: int = 0
    content_hash: str = ""
    heading_level: int | None = None
    heading_path: tuple[str, ...] = ()
    page_start: int | None = None
    page_end: int | None = None
    source_part: str = "document"

    def to_record(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "source_id": self.source_id,
            "range_id": self.range_id,
            "kind": self.kind,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
            "content_hash": self.content_hash,
            "heading_level": self.heading_level,
            "heading_path": list(self.heading_path),
            "page_start": self.page_start,
            "page_end": self.page_end,
            "source_part": self.source_part,
            "character_count": len(self.text),
        }


@dataclass(frozen=True)
class SourceEvidenceRef:
    evidence_id: str
    source_id: str
    segment_id: str
    range_id: str
    char_start: int
    char_end: int
    paragraph_start: int
    paragraph_end: int
    content_hash: str
    extractor_version: str
    confidence: float = 1.0
    page_start: int | None = None
    page_end: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "segment_id": self.segment_id,
            "range_id": self.range_id,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "content_hash": self.content_hash,
            "extractor_version": self.extractor_version,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    source_id: str
    segment_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    heading_paths: tuple[tuple[str, ...], ...]
    text: str = field(repr=False)
    char_start: int = 0
    char_end: int = 0
    paragraph_start: int = 0
    paragraph_end: int = 0

    def to_record(self, *, path: str) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "path": path,
            "source_id": self.source_id,
            "segment_ids": list(self.segment_ids),
            "evidence_refs": list(self.evidence_ids),
            "heading_paths": [list(item) for item in self.heading_paths],
            "char_start": self.char_start,
            "char_end": self.char_end,
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
            "char_count": len(self.text),
        }
