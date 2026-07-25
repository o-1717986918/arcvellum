"""Source reader dispatch for deterministic Project Archaeology imports."""

from __future__ import annotations

from pathlib import Path

from ..contracts import SourceDocument
from .docx import read_docx_document
from .markdown import read_markdown_document
from .text import read_inline_document, read_text_document


SUPPORTED_SOURCE_EXTENSIONS = {".txt", ".md", ".markdown", ".docx"}


def read_source_documents(
    source: Path | None,
    *,
    text: str,
    title: str,
    rights_declaration: str,
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    if source:
        for path in _collect_source_files(source):
            suffix = path.suffix.lower()
            if suffix == ".docx":
                document = read_docx_document(
                    path,
                    title=title if source.is_file() else "",
                    rights_declaration=rights_declaration,
                )
            elif suffix in {".md", ".markdown"}:
                document = read_markdown_document(
                    path,
                    title=title if source.is_file() else "",
                    rights_declaration=rights_declaration,
                )
            else:
                document = read_text_document(
                    path,
                    title=title if source.is_file() else "",
                    rights_declaration=rights_declaration,
                )
            documents.append(document)
    if text:
        documents.append(
            read_inline_document(
                text,
                title=title or "inline-source",
                rights_declaration=rights_declaration,
            )
        )
    if not documents:
        raise ValueError("no readable source documents found")
    return documents


def _collect_source_files(source: Path) -> list[Path]:
    if not source.exists():
        raise FileNotFoundError(f"source path does not exist: {source}")
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            raise ValueError(f"unsupported source extension: {source.suffix}")
        return [source]
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(source)
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(path)
    if not files:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_EXTENSIONS))
        raise ValueError(f"no supported source files ({supported}) found under: {source}")
    return files
