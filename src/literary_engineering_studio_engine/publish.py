"""Chapter publication gate and release artifact writer."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .canon_lint import build_canon_lint
from .chapter_pipeline import build_chapter_workspace
from .export_package import build_export_package


@dataclass(frozen=True)
class PublishChapterResult:
    project_root: Path
    release_dir: Path
    manifest_path: Path
    notes_path: Path
    rollback_path: Path
    latest_path: Path
    chapter_id: str
    release_id: str
    published_scene_count: int
    approval_run_id: str
    status: str


def publish_chapter(
    project_root: Path,
    chapter_id: str = "chapter_0001",
    release_id: str = "",
    approval_run_id: str = "",
    allow_unapproved: bool = False,
    rebuild_chapter: bool = False,
    rebuild_export: bool = False,
    output_dir: Path | None = None,
    overwrite: bool = False,
    export_formats: str = "md",
) -> PublishChapterResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    release_id = _validate_release_id(release_id or _default_release_id())
    release_dir = _resolve_release_dir(root, chapter_id, release_id, output_dir)
    if release_dir.exists() and any(release_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"release directory already exists: {release_dir}")

    canon = build_canon_lint(root)
    if canon.blocking_count:
        raise RuntimeError(f"canon-lint has blocking issues: {canon.blocking_count}")

    chapter = build_chapter_workspace(root, chapter_id=chapter_id, build_missing=False, review_drafts=False)
    if rebuild_chapter:
        chapter = build_chapter_workspace(root, chapter_id=chapter_id, build_missing=False, review_drafts=True)
    if chapter.scene_count <= 0:
        raise RuntimeError(f"chapter has no scenes: {chapter_id}")
    if chapter.blocked_count:
        raise RuntimeError(f"chapter has non-ready scenes: {chapter.blocked_count}")

    approval = _find_approval(root, approval_run_id)
    if approval is None and not allow_unapproved:
        raise RuntimeError("publish requires an approve record; pass approval_run_id or use allow_unapproved for internal release")

    export = build_export_package(
        root,
        chapter_id=chapter_id,
        include_blocked=False,
        rebuild_chapter=rebuild_export,
        formats=export_formats,
    )
    if export.exported_scene_count <= 0:
        raise RuntimeError(f"chapter has no exported scenes: {chapter_id}")
    if export.skipped_scene_count:
        raise RuntimeError(f"export skipped scenes: {export.skipped_scene_count}")

    release_dir.mkdir(parents=True, exist_ok=True)
    copied_outputs = _copy_exports(root, release_dir, export)
    latest_path = root / "releases" / chapter_id / "latest.json"
    manifest_path = release_dir / "publish_manifest.json"
    notes_path = release_dir / "release_notes.md"
    rollback_path = release_dir / "rollback.md"
    previous_latest = _read_json(latest_path)
    published_at = _now()
    warnings = []
    if approval is None:
        warnings.append("发布使用 allow_unapproved，仅可作为内部候选，不建议对外视为正式发布。")
    if canon.warning_count:
        warnings.append(f"canon-lint 存在 {canon.warning_count} 条 warning，已允许发布但应进入后续维护队列。")

    manifest = {
        "schema": "literary-engineering-workbench/publish-chapter/v0.1",
        "published_at": published_at,
        "status": "published_internal" if approval is None else "published",
        "chapter_id": chapter_id,
        "release_id": release_id,
        "project_root": str(root),
        "approval": approval or {"decision": "allow_unapproved", "run_id": "", "notes": ""},
        "gates": {
            "canon_lint": {
                "status": canon.status,
                "report": _rel(canon.report_path, root),
                "json": _rel(canon.json_path, root),
                "blocking_count": canon.blocking_count,
                "warning_count": canon.warning_count,
            },
            "chapter_workspace": {
                "markdown": _rel(chapter.markdown_path, root),
                "json": _rel(chapter.json_path, root),
                "scene_count": chapter.scene_count,
                "ready_count": chapter.ready_count,
                "blocked_count": chapter.blocked_count,
            },
            "export_package": {
                "manifest": _rel(export.manifest_path, root),
                "exported_scene_count": export.exported_scene_count,
                "skipped_scene_count": export.skipped_scene_count,
            },
        },
        "source_artifacts": {
            "export_manifest": _rel(export.manifest_path, root),
            "novel": _rel(export.novel_path, root),
            "screenplay": _rel(export.screenplay_path, root),
            "video_prompt_pack": _rel(export.video_prompt_path, root),
            "docx": {key: _rel(path, root) for key, path in export.docx_outputs.items()},
        },
        "published_outputs": copied_outputs,
        "previous_release": previous_latest,
        "rollback": _rel(rollback_path, root),
        "warnings": warnings,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notes_path.write_text(_render_release_notes(manifest), encoding="utf-8")
    rollback_path.write_text(_render_rollback(manifest), encoding="utf-8")
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/latest-release/v0.1",
                "chapter_id": chapter_id,
                "release_id": release_id,
                "release_dir": _rel(release_dir, root),
                "manifest": _rel(manifest_path, root),
                "published_at": published_at,
                "previous_release_id": str(previous_latest.get("release_id", "")) if previous_latest else "",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return PublishChapterResult(
        project_root=root,
        release_dir=release_dir,
        manifest_path=manifest_path,
        notes_path=notes_path,
        rollback_path=rollback_path,
        latest_path=latest_path,
        chapter_id=chapter_id,
        release_id=release_id,
        published_scene_count=export.exported_scene_count,
        approval_run_id=str((approval or {}).get("run_id", "")),
        status=str(manifest["status"]),
    )


def _copy_exports(root: Path, release_dir: Path, export) -> dict[str, str]:
    targets = {
        "novel": release_dir / export.novel_path.name,
        "screenplay": release_dir / export.screenplay_path.name,
        "video_prompt_pack": release_dir / export.video_prompt_path.name,
        "export_manifest": release_dir / "source_export_manifest.json",
    }
    sources = {
        "novel": export.novel_path,
        "screenplay": export.screenplay_path,
        "video_prompt_pack": export.video_prompt_path,
        "export_manifest": export.manifest_path,
    }
    for key, source in export.docx_outputs.items():
        docx_key = f"{key}_docx"
        sources[docx_key] = source
        targets[docx_key] = release_dir / source.name
    for key, source in sources.items():
        shutil.copyfile(source, targets[key])
    return {key: _rel(path, root) for key, path in targets.items()}


def _find_approval(root: Path, approval_run_id: str = "") -> dict[str, object] | None:
    index_path = root / "workflow" / "approvals" / "index.jsonl"
    if not index_path.exists():
        return None
    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("decision") != "approve":
            continue
        if approval_run_id and record.get("run_id") != approval_run_id:
            continue
        records.append(record)
    if not records:
        return None
    return records[-1]


def _render_release_notes(manifest: dict[str, object]) -> str:
    gates = manifest["gates"]
    outputs = manifest["published_outputs"]
    warnings = manifest.get("warnings", [])
    lines = [
        f"# Release Notes：{manifest['chapter_id']} / {manifest['release_id']}",
        "",
        f"- 状态：`{manifest['status']}`",
        f"- 发布时间：{manifest['published_at']}",
        f"- 审批 run：`{manifest['approval'].get('run_id', '') or 'n/a'}`",
        f"- 发布场景数：{gates['export_package']['exported_scene_count']}",
        f"- Canon Lint：{gates['canon_lint']['status']}，blocking={gates['canon_lint']['blocking_count']}，warning={gates['canon_lint']['warning_count']}",
        "",
        "## 发布文件",
        "",
    ]
    for key, value in outputs.items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 变更摘要", "", "- 本次发布复制章节导出产物，并记录发布门禁、审批记录和回滚入口。"])
    if warnings:
        lines.extend(["", "## 警告", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _render_rollback(manifest: dict[str, object]) -> str:
    previous = manifest.get("previous_release") or {}
    lines = [
        f"# Rollback：{manifest['chapter_id']} / {manifest['release_id']}",
        "",
        "## 当前发布",
        "",
        f"- release_id：`{manifest['release_id']}`",
        f"- manifest：`releases/{manifest['chapter_id']}/{manifest['release_id']}/publish_manifest.json`",
        "",
        "## 回滚目标",
        "",
    ]
    if previous:
        lines.append(f"- previous_release_id：`{previous.get('release_id', '')}`")
        lines.append(f"- previous_manifest：`{previous.get('manifest', '')}`")
    else:
        lines.append("- 当前没有上一版发布记录。")
    lines.extend(
        [
            "",
            "## 操作原则",
            "",
            "- 不删除当前 release 目录。",
            "- 如需回滚，只更新 `releases/{chapter_id}/latest.json` 指向上一版 manifest。",
            "- 回滚后保留本文件作为审计记录。",
        ]
    )
    return "\n".join(lines) + "\n"


def _resolve_release_dir(root: Path, chapter_id: str, release_id: str, output_dir: Path | None) -> Path:
    if output_dir is not None:
        return output_dir if output_dir.is_absolute() else root / output_dir
    return root / "releases" / chapter_id / release_id


def _validate_release_id(value: str) -> str:
    release_id = value.strip()
    if not release_id:
        raise ValueError("release_id must not be empty")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", release_id) or ".." in release_id:
        raise ValueError("release_id may contain only letters, numbers, dot, underscore, and hyphen")
    return release_id


def _default_release_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
