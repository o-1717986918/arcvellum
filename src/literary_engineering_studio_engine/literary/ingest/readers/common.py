"""Shared reader assembly without literary inference."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from ..contracts import EXTRACTOR_VERSION, SourceDocument, SourceRange


@dataclass(frozen=True)
class ExtractedBlock:
    text: str
    kind: str = "paragraph"
    source_part: str = "document"
    style_name: str = ""
    heading_level: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    footnote_id: str = ""


def assemble_document(
    *,
    title: str,
    filename: str,
    media_type: str,
    original_bytes: bytes,
    blocks: list[ExtractedBlock],
    rights_declaration: str,
    extraction_method: str,
    encoding: str = "",
) -> SourceDocument:
    cleaned = [block for block in blocks if block.text.strip()]
    if not cleaned:
        raise ValueError(f"source contains no readable text: {filename}")
    original_hash = sha256_bytes(original_bytes)
    source_id = f"{slug(Path(filename).stem or title or 'source')}-{original_hash[:12]}"
    parts: list[str] = []
    ranges: list[SourceRange] = []
    cursor = 0
    for ordinal, block in enumerate(cleaned, start=1):
        text = normalize_block_text(block.text)
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(text)
        cursor += len(text)
        ranges.append(
            SourceRange(
                range_id=f"{source_id}:range-{ordinal:05d}",
                kind=block.kind,
                ordinal=ordinal,
                char_start=start,
                char_end=cursor,
                paragraph_start=ordinal,
                paragraph_end=ordinal,
                content_hash=sha256_text(text),
                source_part=block.source_part,
                style_name=block.style_name,
                heading_level=block.heading_level,
                page_start=block.page_start,
                page_end=block.page_end,
                footnote_id=block.footnote_id,
            )
        )
    extracted = "".join(parts).rstrip() + "\n"
    return SourceDocument(
        source_id=source_id,
        title=title.strip() or Path(filename).stem or source_id,
        media_type=media_type,
        content_hash=original_hash,
        rights_declaration=rights_declaration.strip(),
        extraction_method=extraction_method,
        bounds=tuple(ranges),
        text=extracted,
        extracted_text_hash=sha256_text(extracted),
        extractor_version=EXTRACTOR_VERSION,
        encoding=encoding,
        original_filename=Path(filename).name,
        original_bytes=original_bytes,
    )


def normalize_block_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def heading_level_for_text(text: str) -> int | None:
    value = text.strip()
    if re.match(r"^(?:第[一二三四五六七八九十百千万零〇\d]+卷|卷[一二三四五六七八九十百千万零〇\d]+)\b", value):
        return 1
    if re.match(r"^(?:第[一二三四五六七八九十百千万零〇\d]+章|chapter\s+\w+)\b", value, re.IGNORECASE):
        return 2
    if re.match(r"^(?:序章|楔子|尾声|后记|prologue|epilogue)\b", value, re.IGNORECASE):
        return 2
    return None


def slug(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", normalized).strip("-")
    return normalized[:48].strip("-") or "source"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))
