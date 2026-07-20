"""DOCX export helpers for final literary artifacts.

The exporter intentionally uses only the Python standard library. It creates a
small, valid WordprocessingML package from Markdown-like chapter exports so the
workbench can deliver editable Word files without adding runtime dependencies.
"""

from __future__ import annotations

import re
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from .draft_text import final_body_from_workbench_text


DOCX_KINDS = {"novel", "screenplay", "video_prompt_pack", "report"}
DELIVERY_TRACE_RE = re.compile(
    r"(scene[_-]?\d{1,6}|chapter[_-]?\d{1,6}|AGENT_TASK|prompt manifest|"
    r"状态变化候选|世界状态变化|人物状态变化|新增事实候选|新角色候选|新角色候选登记|写回候选|需要人工确认|"
    r"上下文包|场景文件|审查状态)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DocxExportResult:
    source_path: Path
    docx_path: Path
    layout_plan_path: Path
    inspection_path: Path
    title: str
    paragraph_count: int
    warning_count: int
    inspection_warnings: tuple[str, ...]


def export_markdown_to_docx(
    source_path: Path,
    output_path: Path | None = None,
    *,
    title: str = "",
    kind: str = "novel",
    overwrite: bool = True,
) -> DocxExportResult:
    """Export a Markdown/text artifact to an editable DOCX file."""

    source = source_path.resolve()
    if not source.exists():
        raise FileNotFoundError(f"source markdown not found: {source}")
    if not source.is_file():
        raise ValueError(f"source must be a file: {source}")

    doc_kind = kind if kind in DOCX_KINDS else "novel"
    out = output_path or source.with_suffix(".docx")
    out = out if out.is_absolute() else source.parent / out
    if out.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    text = source.read_text(encoding="utf-8", errors="ignore")
    inferred_title = title.strip() or _infer_title(text) or source.stem
    text = _delivery_markdown_source(text, title=inferred_title, kind=doc_kind)
    paragraphs, warnings = _markdown_to_paragraphs(text, kind=doc_kind)
    if not paragraphs:
        paragraphs = [_paragraph("未读取到可导出的正文。", style="Normal")]
        warnings.append("source produced no paragraphs")
    layout_plan = _build_layout_plan(text, title=inferred_title, kind=doc_kind, paragraph_count=len(paragraphs), warnings=warnings)
    layout_plan_path = out.parent / f"{out.stem}.layout.json"
    inspection_path = out.parent / f"{out.stem}.inspection.json"
    layout_plan_path.write_text(json.dumps(layout_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_docx(
        out,
        title=inferred_title,
        body_xml="\n".join(paragraphs),
        paragraph_count=len(paragraphs),
        kind=doc_kind,
    )
    inspection = inspect_docx(out)
    inspection_path.write_text(json.dumps(inspection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inspection_warnings = tuple(str(item) for item in inspection.get("warnings", []))
    return DocxExportResult(
        source_path=source,
        docx_path=out,
        layout_plan_path=layout_plan_path,
        inspection_path=inspection_path,
        title=inferred_title,
        paragraph_count=len(paragraphs),
        warning_count=len(warnings) + len(inspection_warnings),
        inspection_warnings=inspection_warnings,
    )


def inspect_docx(path: Path) -> dict[str, object]:
    """Run a lightweight structural check on a generated DOCX package."""

    docx_path = path.resolve()
    if not docx_path.exists():
        raise FileNotFoundError(f"docx not found: {docx_path}")
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "word/document.xml",
        "word/styles.xml",
        "word/numbering.xml",
        "word/settings.xml",
        "word/_rels/document.xml.rels",
    }
    with zipfile.ZipFile(docx_path) as package:
        names = set(package.namelist())
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"invalid DOCX package, missing: {', '.join(missing)}")
        document_xml = package.read("word/document.xml")
        styles_xml = package.read("word/styles.xml")
        numbering_xml = package.read("word/numbering.xml")
        settings_xml = package.read("word/settings.xml")
        document_root = ElementTree.fromstring(document_xml)
        styles_root = ElementTree.fromstring(styles_xml)
        ElementTree.fromstring(numbering_xml)
        ElementTree.fromstring(settings_xml)
    paragraph_count = document_xml.count(b"<w:p")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    document_text = "".join(node.text or "" for node in document_root.findall(".//w:t", ns))
    style_ids = sorted(
        item.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId", "")
        for item in styles_root.findall(".//w:style", ns)
        if item.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId")
    )
    warnings = _docx_inspection_warnings(document_xml, styles_xml, numbering_xml, settings_xml, document_text, style_ids)
    return {
        "path": str(docx_path),
        "paragraph_count": paragraph_count,
        "table_count": document_xml.count(b"<w:tbl>"),
        "text_chars": len(document_text),
        "cjk_chars": len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", document_text)),
        "styles": style_ids,
        "has_numbering": b"<w:numbering" in numbering_xml,
        "has_page_size": b"<w:pgSz" in document_xml,
        "has_page_margins": b"<w:pgMar" in document_xml,
        "has_east_asia_fonts": b"w:eastAsia" in styles_xml,
        "warnings": warnings,
        "missing": [],
    }


def _infer_title(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line:
            return line[:80]
    return ""


def _delivery_markdown_source(text: str, *, title: str, kind: str) -> str:
    if kind == "report":
        return text
    if not re.search(r"(?m)^##\s*(正文草稿|正文候选|修订正文候选)\s*$", text):
        return text
    body = final_body_from_workbench_text(text)
    return f"# {title}\n\n{body}\n" if body else f"# {title}\n\n未读取到可导出的正文。\n"


def _markdown_to_paragraphs(text: str, *, kind: str) -> tuple[list[str], list[str]]:
    paragraphs: list[str] = []
    warnings: list[str] = []
    in_code = False
    code_buffer: list[str] = []
    heading1_seen = False
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                if code_buffer:
                    paragraphs.extend(_code_paragraph(item) for item in code_buffer)
                code_buffer = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_buffer.append(line)
            index += 1
            continue
        if not stripped:
            index += 1
            continue
        if re.fullmatch(r"[-*_]{3,}", stripped):
            paragraphs.append(_paragraph("", style="Spacer"))
            index += 1
            continue
        if _is_table_start(lines, index):
            rows, next_index = _parse_table(lines, index)
            if rows:
                paragraphs.append(_table(rows))
            else:
                warnings.append("markdown table could not be parsed")
            index = next_index
            continue
        if stripped.startswith("# "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="Title", alignment="center"))
            index += 1
            continue
        if stripped.startswith("## "):
            page_break = heading1_seen and kind in {"novel", "screenplay"}
            heading1_seen = True
            paragraphs.append(_paragraph(stripped[3:].strip(), style="Heading1", page_break_before=page_break))
            index += 1
            continue
        if stripped.startswith("### "):
            paragraphs.append(_paragraph(stripped[4:].strip(), style="Heading2"))
            index += 1
            continue
        if stripped.startswith("#### "):
            paragraphs.append(_paragraph(stripped[5:].strip(), style="Heading3"))
            index += 1
            continue
        if stripped.startswith("> "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="Quote"))
            index += 1
            continue
        if stripped.startswith("- "):
            paragraphs.append(_paragraph(stripped[2:].strip(), style="ListParagraph", numbering="bullet"))
            index += 1
            continue
        number_match = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if number_match:
            paragraphs.append(_paragraph(number_match.group(2).strip(), style="ListParagraph", numbering="number"))
            index += 1
            continue
        paragraphs.append(_paragraph(stripped, style="Normal"))
        index += 1

    if in_code:
        warnings.append("unclosed code fence")
        paragraphs.extend(_code_paragraph(item) for item in code_buffer)
    return paragraphs, warnings


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    first = lines[index].strip()
    second = lines[index + 1].strip()
    if "|" not in first or "|" not in second:
        return False
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", second))


def _parse_table(lines: list[str], index: int) -> tuple[list[list[str]], int]:
    rows = [_split_table_row(lines[index])]
    index += 2
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or "|" not in stripped:
            break
        rows.append(_split_table_row(stripped))
        index += 1
    max_cols = max((len(row) for row in rows), default=0)
    normalized = [row + [""] * (max_cols - len(row)) for row in rows if any(cell.strip() for cell in row)]
    return normalized, index


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _table(rows: list[list[str]]) -> str:
    col_count = max((len(row) for row in rows), default=1)
    width = max(9000 // max(col_count, 1), 1200)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(col_count))
    row_xml = []
    for row_index, row in enumerate(rows):
        cells = []
        for cell in row:
            shading = '<w:shd w:fill="EAF2F8" w:val="clear"/>' if row_index == 0 else ""
            text_xml = "".join(_inline_runs(cell))
            bold = "<w:rPr><w:b/><w:bCs/></w:rPr>" if row_index == 0 else ""
            if bold:
                text_xml = "".join(_run(cell, bold=True))
            cells.append(
                f'''<w:tc>
  <w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shading}</w:tcPr>
  <w:p><w:pPr><w:spacing w:before="80" w:after="80"/></w:pPr>{text_xml}</w:p>
</w:tc>'''
            )
        row_xml.append(f"<w:tr>{''.join(cells)}</w:tr>")
    return f'''<w:tbl>
  <w:tblPr>
    <w:tblStyle w:val="TableGrid"/>
    <w:tblW w:w="0" w:type="auto"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      <w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      <w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      <w:insideV w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tblGrid>{grid}</w:tblGrid>
  {''.join(row_xml)}
</w:tbl>'''


def _code_paragraph(text: str) -> str:
    return _paragraph(text or " ", style="Code")


def _paragraph(
    text: str,
    *,
    style: str = "Normal",
    alignment: str = "",
    numbering: str = "",
    page_break_before: bool = False,
) -> str:
    ppr: list[str] = []
    if style and style != "Normal":
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if numbering == "bullet":
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
    elif numbering == "number":
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>')
    if page_break_before:
        ppr.append("<w:pageBreakBefore/>")
    ppr.append('<w:spacing w:before="0" w:after="160" w:line="360" w:lineRule="auto"/>')
    if alignment:
        ppr.append(f'<w:jc w:val="{alignment}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>"
    run_xml = "".join(_inline_runs(text))
    return f"<w:p>{ppr_xml}{run_xml}</w:p>"


def _inline_runs(text: str) -> Iterable[str]:
    if not text:
        yield "<w:r><w:t></w:t></w:r>"
        return
    pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            yield _run(text[pos : match.start()])
        token = match.group(0)
        if token.startswith("**"):
            yield _run(token[2:-2], bold=True)
        elif token.startswith("`"):
            yield _run(token[1:-1], code=True)
        pos = match.end()
    if pos < len(text):
        yield _run(text[pos:])


def _run(text: str, *, bold: bool = False, code: bool = False) -> str:
    props = []
    if bold:
        props.append("<w:b/><w:bCs/>")
    if code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    space = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f"<w:r>{rpr}<w:t{space}>{escape(text)}</w:t></w:r>"


def _build_layout_plan(text: str, *, title: str, kind: str, paragraph_count: int, warnings: list[str]) -> dict[str, object]:
    stats = _markdown_stats(text)
    presets = {
        "novel": {
            "page": "A4 portrait",
            "body_font": "SimSun 12pt for Chinese, Times New Roman 12pt for Latin",
            "line_spacing": "1.5 lines",
            "chapter_breaks": "Heading1 starts later major sections on a new page",
        },
        "screenplay": {
            "page": "A4 portrait",
            "body_font": "SimSun 12pt for Chinese, Times New Roman 12pt for Latin",
            "line_spacing": "1.5 lines",
            "chapter_breaks": "major scene groups start on a new page",
        },
        "video_prompt_pack": {
            "page": "A4 portrait",
            "body_font": "Microsoft YaHei / SimSun for Chinese, Calibri for Latin",
            "line_spacing": "1.5 lines",
            "chapter_breaks": "prompt sections keep structured headings and real lists",
        },
        "report": {
            "page": "A4 portrait",
            "body_font": "Microsoft YaHei / SimSun for Chinese, Calibri for Latin",
            "line_spacing": "1.5 lines",
            "chapter_breaks": "report sections use Word heading hierarchy",
        },
    }
    return {
        "schema": "literary-engineering-workbench/docx-layout-plan/v0.2",
        "title": title,
        "kind": kind,
        "preset": presets.get(kind, presets["novel"]),
        "source_structure": stats,
        "word_styles": ["Title", "Subtitle", "Heading1", "Heading2", "Heading3", "Normal", "Quote", "Code", "ListParagraph", "TableGrid"],
        "quality_gates": [
            "editable WordprocessingML, not flattened image output",
            "structured headings with outline levels",
            "real Word numbering for bullets and numbered lists",
            "native Word tables for simple Markdown tables",
            "East Asian font declared for Chinese text",
            "package parts validated after generation",
            "inspection report written beside DOCX",
        ],
        "paragraph_xml_blocks": paragraph_count,
        "warnings": list(warnings),
    }


def _markdown_stats(text: str) -> dict[str, int]:
    lines = text.splitlines()
    return {
        "heading1_count": sum(1 for line in lines if line.startswith("# ")),
        "heading2_count": sum(1 for line in lines if line.startswith("## ")),
        "heading3_count": sum(1 for line in lines if line.startswith("### ")),
        "bullet_count": sum(1 for line in lines if line.strip().startswith("- ")),
        "numbered_count": sum(1 for line in lines if re.match(r"^\s*\d+[.)]\s+", line)),
        "table_count": sum(1 for index in range(len(lines)) if _is_table_start(lines, index)),
        "code_block_fence_count": sum(1 for line in lines if line.strip().startswith("```")),
        "cjk_char_count": len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)),
    }


def _docx_inspection_warnings(
    document_xml: bytes,
    styles_xml: bytes,
    numbering_xml: bytes,
    settings_xml: bytes,
    document_text: str,
    style_ids: list[str],
) -> list[str]:
    warnings: list[str] = []
    required_styles = {"Normal", "Title", "Heading1", "Heading2", "Heading3", "ListParagraph"}
    missing_styles = sorted(required_styles - set(style_ids))
    if missing_styles:
        warnings.append("missing required styles: " + ", ".join(missing_styles))
    if b"w:eastAsia" not in styles_xml:
        warnings.append("styles.xml does not declare East Asian fonts")
    if b"<w:numbering" not in numbering_xml:
        warnings.append("numbering.xml does not contain numbering definitions")
    if b"<w:pgSz" not in document_xml or b"<w:pgMar" not in document_xml:
        warnings.append("document.xml lacks explicit page size or margins")
    if b"<w:docGrid" not in document_xml:
        warnings.append("document.xml lacks docGrid line pitch")
    if b"<w:characterSpacingControl" not in settings_xml:
        warnings.append("settings.xml lacks character spacing control")
    if "\ufffd" in document_text:
        warnings.append("document text contains replacement characters, possible garbled source text")
    if re.search(r"(?m)^\s*[•●○]\s+", document_text):
        warnings.append("document text may contain fake bullet characters instead of Word numbering")
    if DELIVERY_TRACE_RE.search(document_text):
        warnings.append("document text may contain workbench traces; export from a cleaned package or review draft_text cleaning rules")
    return warnings


def _write_docx(path: Path, *, title: str, body_xml: str, paragraph_count: int, kind: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _content_types())
        package.writestr("_rels/.rels", _root_rels())
        package.writestr("docProps/core.xml", _core_props(title, timestamp))
        package.writestr("docProps/app.xml", _app_props(paragraph_count))
        package.writestr("word/_rels/document.xml.rels", _document_rels())
        package.writestr("word/styles.xml", _styles())
        package.writestr("word/numbering.xml", _numbering())
        package.writestr("word/settings.xml", _settings())
        package.writestr("word/document.xml", _document(title, body_xml, kind))


def _document(title: str, body_xml: str, kind: str) -> str:
    subject = {
        "novel": "长篇正文 DOCX 导出",
        "screenplay": "剧本工作稿 DOCX 导出",
        "video_prompt_pack": "长视频提示词包 DOCX 导出",
        "report": "文档 DOCX 导出",
    }.get(kind, "DOCX 导出")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Subtitle"/><w:jc w:val="center"/></w:pPr>
      <w:r><w:t>{escape(subject)}</w:t></w:r>
    </w:p>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="312"/>
    </w:sectPr>
  </w:body>
</w:document>
'''


def _content_types() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>
'''


def _root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'''


def _document_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>
'''


def _core_props(title: str, timestamp: str) -> str:
    safe_title = escape(title)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{safe_title}</dc:title>
  <dc:creator>literary-engineering-workbench</dc:creator>
  <cp:lastModifiedBy>literary-engineering-workbench</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>
</cp:coreProperties>
'''


def _app_props(paragraph_count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>literary-engineering-workbench</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Paragraphs>{paragraph_count}</Paragraphs>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>0.1</AppVersion>
</Properties>
'''


def _styles() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="160" w:line="360" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="240"/><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:pPr><w:spacing w:after="120"/><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:color w:val="666666"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="360" w:after="240"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="240" w:after="180"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="Heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr><w:spacing w:before="160" w:after="120"/><w:outlineLvl w:val="2"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:b/><w:bCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Quote">
    <w:name w:val="Quote"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720" w:right="720"/><w:spacing w:before="120" w:after="120"/></w:pPr>
    <w:rPr><w:i/><w:iCs/><w:color w:val="555555"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Code">
    <w:name w:val="Code"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="80" w:after="80"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Spacer">
    <w:name w:val="Spacer"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:basedOn w:val="TableNormal"/>
    <w:uiPriority w:val="59"/>
    <w:tblPr>
      <w:tblBorders>
        <w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
        <w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
        <w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
        <w:insideV w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
      </w:tblBorders>
    </w:tblPr>
  </w:style>
</w:styles>
'''


def _numbering() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>
'''


def _settings() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>
'''
