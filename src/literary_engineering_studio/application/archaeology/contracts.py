"""Transport-independent contracts for source-work import."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from literary_engineering_studio_engine.projects.source_ingest import (
    INGEST_MODES,
    TEXT_EXTENSIONS,
)


MAX_SOURCE_BYTES = 25 * 1024 * 1024
MODE_PRESENTATION = {
    "continuation": {
        "label": "续写基础",
        "intent": "优先恢复 Canon、人物状态、未结承诺和可继续发展的空间。",
    },
    "rewrite": {
        "label": "改写重构",
        "intent": "优先识别结构问题、保留项、可替换事件和关系压力。",
    },
    "adaptation": {
        "label": "媒介改编",
        "intent": "优先识别可场景化事件、媒介转换风险和角色合并候选。",
    },
    "analysis": {
        "label": "作品分析",
        "intent": "只形成证据化分析，不创建可晋升的正式资产候选。",
    },
}


@dataclass(frozen=True)
class ArchaeologyImportSpec:
    filename: str
    content: bytes
    title: str
    work_id: str
    mode: str
    rights_declaration: str
    chunk_size: int = 6000
    overwrite: bool = False

    @classmethod
    def create(
        cls,
        *,
        filename: str,
        text: str = "",
        content_base64: str = "",
        title: str,
        work_id: str,
        mode: str,
        rights_declaration: str,
        chunk_size: int = 6000,
        overwrite: bool = False,
    ) -> "ArchaeologyImportSpec":
        safe_name = Path(filename).name.strip()
        suffix = Path(safe_name).suffix.lower()
        if not safe_name or suffix not in TEXT_EXTENSIONS:
            supported = ", ".join(sorted(TEXT_EXTENSIONS))
            raise ValueError(f"source filename must use a supported extension: {supported}")
        if mode not in INGEST_MODES:
            raise ValueError(f"unknown Project Archaeology mode: {mode}")
        if not rights_declaration.strip():
            raise ValueError("rights declaration is required before source import")
        if bool(text) == bool(content_base64):
            raise ValueError("provide exactly one of text or content_base64")
        content = _decode_content(text, content_base64)
        if not content:
            raise ValueError("source content is empty")
        if len(content) > MAX_SOURCE_BYTES:
            raise ValueError(f"source content exceeds {MAX_SOURCE_BYTES} bytes")
        if suffix == ".docx" and text:
            raise ValueError("DOCX source must be uploaded as content_base64")
        if chunk_size < 1000 or chunk_size > 20000:
            raise ValueError("chunk_size must be between 1000 and 20000")
        return cls(
            filename=safe_name,
            content=content,
            title=title.strip(),
            work_id=work_id.strip(),
            mode=mode,
            rights_declaration=rights_declaration.strip(),
            chunk_size=chunk_size,
            overwrite=overwrite,
        )


def mode_catalog() -> list[dict[str, str]]:
    return [
        {"id": mode, **presentation}
        for mode, presentation in MODE_PRESENTATION.items()
    ]


def _decode_content(text: str, content_base64: str) -> bytes:
    if text:
        return text.encode("utf-8")
    try:
        return base64.b64decode(content_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("content_base64 is invalid") from exc
