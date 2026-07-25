"""Dependency-free DOCX reader for body, styles, headings, and footnotes."""

from __future__ import annotations

from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

from ..contracts import SourceDocument
from .common import ExtractedBlock, assemble_document, heading_level_for_text


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"
NS = {"w": WORD_NS}
DOCUMENT_PART = "word/document.xml"
STYLES_PART = "word/styles.xml"
FOOTNOTES_PART = "word/footnotes.xml"


def read_docx_document(
    path: Path,
    *,
    title: str,
    rights_declaration: str,
) -> SourceDocument:
    original = path.read_bytes()
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            if DOCUMENT_PART not in names:
                raise ValueError(f"invalid DOCX package, missing {DOCUMENT_PART}")
            document = ElementTree.fromstring(package.read(DOCUMENT_PART))
            styles = _style_catalog(
                ElementTree.fromstring(package.read(STYLES_PART))
                if STYLES_PART in names
                else None
            )
            footnotes = _footnote_catalog(
                ElementTree.fromstring(package.read(FOOTNOTES_PART))
                if FOOTNOTES_PART in names
                else None
            )
    except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError(f"invalid DOCX source: {path.name}") from exc

    body_blocks, referenced_footnotes = _body_blocks(document, styles)
    blocks = [
        *body_blocks,
        *_footnote_blocks(footnotes, referenced_footnotes),
    ]
    inferred_title = title or next(
        (block.text for block in body_blocks if block.kind == "heading"),
        path.stem,
    )
    return assemble_document(
        title=inferred_title,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_bytes=original,
        blocks=blocks,
        rights_declaration=rights_declaration,
        extraction_method="docx-openxml-v1",
        encoding="openxml-utf8",
    )


def _body_blocks(
    document: ElementTree.Element,
    styles: dict[str, tuple[str, int | None]],
) -> tuple[list[ExtractedBlock], list[str]]:
    body = document.find(".//w:body", NS)
    if body is None:
        return [], []
    blocks: list[ExtractedBlock] = []
    footnote_order: list[str] = []
    for child in body:
        if child.tag == f"{W}p":
            block, footnotes = _paragraph_block(child, styles, source_part="document")
            if block:
                blocks.append(block)
            footnote_order.extend(item for item in footnotes if item not in footnote_order)
        elif child.tag == f"{W}tbl":
            for paragraph in child.iter(f"{W}p"):
                block, footnotes = _paragraph_block(paragraph, styles, source_part="table")
                if block:
                    blocks.append(block)
                footnote_order.extend(item for item in footnotes if item not in footnote_order)
    return blocks, footnote_order


def _paragraph_block(
    paragraph: ElementTree.Element,
    styles: dict[str, tuple[str, int | None]],
    *,
    source_part: str,
) -> tuple[ExtractedBlock | None, list[str]]:
    text, footnotes = _paragraph_text(paragraph)
    if not text.strip():
        return None, footnotes
    style_node = paragraph.find("./w:pPr/w:pStyle", NS)
    style_id = style_node.attrib.get(f"{W}val", "") if style_node is not None else ""
    style_name, outline_level = styles.get(style_id, (style_id, None))
    heading_level = outline_level or _heading_level(style_id, style_name) or heading_level_for_text(text)
    return (
        ExtractedBlock(
            text=text,
            kind="heading" if heading_level else "paragraph",
            source_part=source_part,
            style_name=style_name or style_id or "Normal",
            heading_level=heading_level,
        ),
        footnotes,
    )


def _paragraph_text(paragraph: ElementTree.Element) -> tuple[str, list[str]]:
    parts: list[str] = []
    footnotes: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag == f"{W}tab":
            parts.append("\t")
        elif node.tag in {f"{W}br", f"{W}cr"}:
            parts.append("\n")
        elif node.tag == f"{W}footnoteReference":
            footnote_id = node.attrib.get(f"{W}id", "")
            if footnote_id:
                parts.append(f"〔脚注{footnote_id}〕")
                footnotes.append(footnote_id)
    return "".join(parts), footnotes


def _style_catalog(root: ElementTree.Element | None) -> dict[str, tuple[str, int | None]]:
    catalog: dict[str, tuple[str, int | None]] = {}
    if root is None:
        return catalog
    for style in root.findall(".//w:style", NS):
        style_id = style.attrib.get(f"{W}styleId", "")
        if not style_id:
            continue
        name_node = style.find("./w:name", NS)
        outline_node = style.find("./w:pPr/w:outlineLvl", NS)
        name = name_node.attrib.get(f"{W}val", "") if name_node is not None else style_id
        outline = _outline_level(outline_node.attrib.get(f"{W}val", "")) if outline_node is not None else None
        catalog[style_id] = (name, outline)
    return catalog


def _footnote_catalog(root: ElementTree.Element | None) -> dict[str, str]:
    catalog: dict[str, str] = {}
    if root is None:
        return catalog
    for footnote in root.findall(".//w:footnote", NS):
        footnote_id = footnote.attrib.get(f"{W}id", "")
        if not footnote_id or footnote_id.startswith("-") or footnote_id == "0":
            continue
        text = "\n".join(
            value
            for paragraph in footnote.findall(".//w:p", NS)
            if (value := _paragraph_text(paragraph)[0].strip())
        )
        if text:
            catalog[footnote_id] = text
    return catalog


def _footnote_blocks(catalog: dict[str, str], reference_order: list[str]) -> list[ExtractedBlock]:
    ordered = [*reference_order, *sorted(set(catalog) - set(reference_order), key=_numeric_key)]
    return [
        ExtractedBlock(
            text=f"脚注 {footnote_id}：{catalog[footnote_id]}",
            kind="footnote",
            source_part="footnotes",
            style_name="FootnoteText",
            footnote_id=footnote_id,
        )
        for footnote_id in ordered
        if footnote_id in catalog
    ]


def _heading_level(style_id: str, style_name: str) -> int | None:
    for value in (style_id, style_name):
        match = re.search(r"(?:heading|标题)\s*([1-6])", value, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _outline_level(value: str) -> int | None:
    try:
        parsed = int(value) + 1
    except (TypeError, ValueError):
        return None
    return parsed if 1 <= parsed <= 9 else None


def _numeric_key(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return 1_000_000, value
