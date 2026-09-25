"""On-demand DOCX snapshot of already committed prose, independent of final release."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    export_markdown_to_docx, formal_chapter_ids, formal_scene_ids_for_chapter,
)
from literary_engineering_studio_engine.public.projects import atomic_write_text
from literary_engineering_studio_engine.public.projections import final_body_from_workbench_text

from .whole_book_release import SCENE_HEADING, TRACE_PATTERN, _file_record, _formal_chapter_sources, _project_title, _rel


def create_partial_docx(project_root: Path) -> dict[str, Any]:
    """Package a point-in-time set of formal scenes without claiming book completion."""

    root = project_root.expanduser().resolve()
    sections, sources = _committed_sections(root)
    if not sections:
        sections, sources = _chapter_sections(root)
    if not sections:
        raise ValueError("还没有可用于当前稿 DOCX 的已晋升正文。")
    title = _project_title(root)
    manuscript = f"# {title}（当前稿）\n\n" + "\n\n".join(sections).strip() + "\n"
    if TRACE_PATTERN.search(manuscript):
        raise ValueError("当前正式正文仍包含工作流痕迹，暂不能创建 DOCX 快照。")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"{stamp}-{uuid4().hex[:8]}"
    output = root / "exports" / "snapshots" / snapshot_id
    markdown = output / "current-manuscript.md"
    docx = output / "current-manuscript.docx"
    atomic_write_text(markdown, manuscript)
    result = export_markdown_to_docx(markdown, docx, title=f"{title}（当前稿）", kind="novel", overwrite=True)
    if result.inspection_warnings:
        raise RuntimeError("当前稿 DOCX 检查未通过：" + "；".join(result.inspection_warnings))
    manifest = {
        "schema": "arcvellum/partial-delivery/v1",
        "status": "partial_snapshot",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "source_prose": sources,
        "outputs": {"markdown": _file_record(markdown, root), "docx": _file_record(docx, root)},
        "note": "仅包含创建时已晋升的正文；不是全书正式发布或完稿审计。",
    }
    atomic_write_text(output / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, "status": "partial_snapshot", "manifest": manifest,
            "docx_path": _rel(docx, root), "markdown_path": _rel(markdown, root)}


def _committed_sections(root: Path) -> tuple[list[str], list[str]]:
    sections: list[str] = []
    sources: list[str] = []
    titles = _chapter_titles(root)
    for index, chapter_id in enumerate(formal_chapter_ids(root), start=1):
        chapter_parts = []
        for scene_id in formal_scene_ids_for_chapter(root, chapter_id):
            prose = root / "drafts" / "scenes" / f"{scene_id}.md"
            receipt = root / "workflow" / "scene_commits" / f"{scene_id}.json"
            if not receipt.is_file() or not prose.is_file():
                continue
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            content = prose.read_text(encoding="utf-8").rstrip()
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if digest != str(payload.get("prose_sha256") or ""):
                raise ValueError(f"正式场景 {scene_id} 的正文与提交回执不一致。")
            body = SCENE_HEADING.sub("", final_body_from_workbench_text(content)).strip()
            if body:
                chapter_parts.append(body)
                sources.append(_rel(prose, root))
        if chapter_parts:
            heading = f"第{index}章"
            if title := titles.get(chapter_id):
                heading += f" {title}"
            sections.append(f"## {heading}\n\n" + "\n\n".join(chapter_parts))
    return sections, sources


def _chapter_titles(root: Path) -> dict[str, str]:
    path = root / "plot" / "lean_project_plan.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if not isinstance(chapters, list):
        return {}
    return {str(item.get("chapter_id") or ""): str(item.get("title") or "").strip()
            for item in chapters if isinstance(item, dict)}


def _chapter_sections(root: Path) -> tuple[list[str], list[str]]:
    sections = []
    sources = []
    for path in _formal_chapter_sources(root):
        body = final_body_from_workbench_text(path.read_text(encoding="utf-8")).strip()
        if body:
            sections.append(body)
            sources.append(_rel(path, root))
    return sections, sources


__all__ = ["create_partial_docx"]
