"""UTF-8 text and inline source readers."""

from __future__ import annotations

from pathlib import Path

from ..contracts import SourceDocument
from .common import ExtractedBlock, assemble_document, heading_level_for_text


def read_text_document(
    path: Path,
    *,
    title: str,
    rights_declaration: str,
) -> SourceDocument:
    original = path.read_bytes()
    text, encoding = _decode_utf8(original, path.name)
    return assemble_document(
        title=title or path.stem,
        filename=path.name,
        media_type="text/plain",
        original_bytes=original,
        blocks=_plain_blocks(text),
        rights_declaration=rights_declaration,
        extraction_method="utf8-text-v1",
        encoding=encoding,
    )


def read_inline_document(
    text: str,
    *,
    title: str,
    rights_declaration: str,
) -> SourceDocument:
    original = text.encode("utf-8")
    return assemble_document(
        title=title,
        filename=f"{title or 'inline-source'}.txt",
        media_type="text/plain",
        original_bytes=original,
        blocks=_plain_blocks(text),
        rights_declaration=rights_declaration,
        extraction_method="inline-text-v1",
        encoding="utf-8",
    )


def _decode_utf8(value: bytes, filename: str) -> tuple[str, str]:
    try:
        return value.decode("utf-8-sig"), "utf-8-sig" if value.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError as exc:
        raise ValueError(f"source text must be valid UTF-8: {filename}") from exc


def _plain_blocks(text: str) -> list[ExtractedBlock]:
    blocks: list[ExtractedBlock] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        value = line.strip()
        if not value:
            continue
        heading_level = heading_level_for_text(value)
        blocks.append(
            ExtractedBlock(
                text=value,
                kind="heading" if heading_level else "paragraph",
                heading_level=heading_level,
                style_name="plain-text-heading" if heading_level else "plain-text",
            )
        )
    return blocks
