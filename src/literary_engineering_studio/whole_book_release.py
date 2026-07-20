"""Whole-book release assembly from already formal chapter artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from literary_engineering_studio_engine.docx_export import export_markdown_to_docx
from literary_engineering_studio_engine.draft_text import final_body_from_workbench_text

from .advisor_snapshot import project_hashes
from .core_bridge import CoreBridge


RELEASE_SCHEMA = "arcvellum/whole-book-release/v0.1"
TRACE_PATTERN = re.compile(
    r"AGENT_TASK|workflow/tasks|branch_manifest|roleplay_simulation|prompt manifest|"
    r"(?:^|\n)#{1,4}\s*(?:Canon|AgentReview|状态变化候选|世界状态变化|人物状态变化|写回候选)",
    re.IGNORECASE,
)
SCENE_HEADING = re.compile(r"(?m)^#{1,6}\s*(?:scene[_-]?\d{1,6}|场景\s*\d{1,6})\s*$\n?")


class WholeBookReleaseCoordinator:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.bridge = CoreBridge(config)

    def release(self, project_root: Path, *, approved_by: str, autopilot_run_id: str = "") -> dict[str, Any]:
        root = project_root.expanduser().resolve()
        sources = _formal_chapter_sources(root)
        if not sources:
            raise RuntimeError("还没有可汇总的正式章节，请先完成导出路线。")
        audits = {}
        for route in ("longform-planning", "scene-development", "review-and-audit", "export-and-release"):
            result = self.bridge.route_audit(root, route)
            audits[route] = result.fields
            blocking = int(result.fields.get("blocking_count") or 0)
            if blocking:
                raise RuntimeError(f"{route} 仍有 {blocking} 项正式门禁未通过，不能生成全书交付。")

        title = _project_title(root)
        sections = []
        for source in sources:
            body = final_body_from_workbench_text(source.read_text(encoding="utf-8", errors="ignore")).strip()
            body = SCENE_HEADING.sub("", body).strip()
            if body:
                sections.append(body)
        if not sections:
            raise RuntimeError("正式章节没有可交付正文。")
        manuscript = f"# {title}\n\n" + "\n\n".join(sections).strip() + "\n"
        if TRACE_PATTERN.search(manuscript):
            raise RuntimeError("全书汇总仍包含工作流痕迹，已停止发布。")

        release_root = root / "releases" / "whole-book"
        release_root.mkdir(parents=True, exist_ok=True)
        markdown = release_root / f"{_safe_name(title)}-complete.md"
        docx = markdown.with_suffix(".docx")
        markdown.write_text(manuscript, encoding="utf-8")
        docx_result = export_markdown_to_docx(markdown, docx, title=title, kind="novel", overwrite=True)
        if docx_result.inspection_warnings:
            raise RuntimeError("DOCX 检查未通过：" + "；".join(docx_result.inspection_warnings))

        snapshot = project_hashes(root)
        snapshot_digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()
        manifest = {
            "schema": RELEASE_SCHEMA,
            "status": "released",
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": approved_by,
            "principal_type": "delegated-agent" if approved_by.startswith("delegated-agent") else "user",
            "autopilot_run_id": autopilot_run_id,
            "project_snapshot_digest": snapshot_digest,
            "source_chapters": [_rel(path, root) for path in sources],
            "formal_audits": audits,
            "outputs": {
                "markdown": _file_record(markdown, root),
                "docx": _file_record(docx, root),
                "docx_layout": _file_record(docx_result.layout_plan_path, root),
                "docx_inspection": _file_record(docx_result.inspection_path, root),
            },
            "clean_delivery_checks": {
                "workflow_trace_free": True,
                "scene_heading_free": not bool(SCENE_HEADING.search(manuscript)),
                "docx_inspection_warnings": 0,
            },
        }
        manifest_path = release_root / "release_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_root = root / "workflow" / "release_reports"
        report_root.mkdir(parents=True, exist_ok=True)
        report_path = report_root / "whole-book-release.md"
        report_path.write_text(_report(manifest), encoding="utf-8")
        return {"ok": True, "manifest": manifest, "manifest_path": _rel(manifest_path, root), "report_path": _rel(report_path, root)}


def _formal_chapter_sources(root: Path) -> list[Path]:
    published = sorted(root.glob("releases/*/formal-release/*_novel.md"), key=lambda path: path.as_posix())
    if published:
        return published
    return sorted(root.glob("exports/*/*_novel.md"), key=lambda path: path.as_posix())


def _project_title(root: Path) -> str:
    text = (root / "project.yaml").read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"(?m)^title:\s*[\"']?(.*?)[\"']?\s*$", text)
    return (match.group(1).strip() if match else root.name) or "完整作品"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "-", value).strip(" .-")
    return cleaned[:80] or "complete-work"


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": _rel(path, root), "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _report(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 全书交付报告",
            "",
            f"- 状态：{manifest['status']}",
            f"- 作品：{manifest['title']}",
            f"- 正式章节：{len(manifest['source_chapters'])}",
            f"- Markdown：{manifest['outputs']['markdown']['path']}",
            f"- DOCX：{manifest['outputs']['docx']['path']}",
            "- 工作流痕迹检查：通过",
            "- DOCX 结构检查：通过",
            "",
        ]
    )
