"""Markdown reader with deterministic heading and paragraph boundaries."""

from __future__ import annotations

from pathlib import Path
import re

from ..contracts import SourceDocument
from .common import ExtractedBlock, assemble_document, heading_level_for_text
from .text import _decode_utf8


def read_markdown_document(
    path: Path,
    *,
    title: str,
    rights_declaration: str,
) -> SourceDocument:
    original = path.read_bytes()
    text, encoding = _decode_utf8(original, path.name)
    blocks = _markdown_blocks(text)
    inferred_title = title or next(
        (block.text for block in blocks if block.kind == "heading"),
        path.stem,
    )
    return assemble_document(
        title=inferred_title,
        filename=path.name,
        media_type="text/markdown",
        original_bytes=original,
        blocks=blocks,
        rights_declaration=rights_declaration,
        extraction_method="markdown-structure-v1",
        encoding=encoding,
    )


def _markdown_blocks(text: str) -> list[ExtractedBlock]:
    blocks: list[ExtractedBlock] = []
    paragraph: list[str] = []
    fenced = False

    def flush() -> None:
        if paragraph:
            blocks.append(ExtractedBlock(text="\n".join(paragraph), style_name="markdown-paragraph"))
            paragraph.clear()

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.rstrip()
        if line.lstrip().startswith("```"):
            fenced = not fenced
            paragraph.append(line)
            continue
        match = None if fenced else re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            flush()
            blocks.append(
                ExtractedBlock(
                    text=match.group(2).strip(),
                    kind="heading",
                    heading_level=len(match.group(1)),
                    style_name=f"markdown-heading-{len(match.group(1))}",
                )
            )
            continue
        if not line.strip() and not fenced:
            flush()
            continue
        paragraph.append(line)
    flush()
    for index, block in enumerate(blocks):
        if block.kind != "paragraph":
            continue
        inferred = heading_level_for_text(block.text)
        if inferred:
            blocks[index] = ExtractedBlock(
                text=block.text,
                kind="heading",
                heading_level=inferred,
                style_name="markdown-semantic-heading",
            )
    return blocks
