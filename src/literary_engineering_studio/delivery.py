"""User-facing delivery history built from formal export and release artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core_read_models import build_dashboard


DELIVERY_ROOTS = ("exports", "releases")
DELIVERY_SUFFIXES = {".docx", ".pdf", ".html", ".md", ".txt", ".zip"}
CONTENT_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".html": "text/html; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".zip": "application/zip",
}


def build_delivery(
    config: dict[str, Any],
    project_root: Path,
    *,
    dashboard_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else build_dashboard(config, project_root)
    route = next(
        (item for item in dashboard.get("route_audits", []) if item.get("route") == "export-and-release"),
        {},
    )
    files = _delivery_files(project_root)
    blocking = int(route.get("blocking_count") or 0)
    pending = int(route.get("pending_task_count") or 0)
    if files and not blocking and not pending:
        status = "ready"
        headline = "作品已经具备可下载的正式交付文件。"
    elif files:
        status = "attention"
        headline = "已有交付文件，但正式路线仍有待处理事项。"
    else:
        status = "pending"
        headline = "还没有正式交付文件，需要继续完成导出路线。"
    return {
        "ok": True,
        "project_root": str(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "headline": headline,
        "route": route,
        "files": files,
        "summary": {
            "file_count": len(files),
            "blocking_count": blocking,
            "pending_task_count": pending,
            "latest_path": files[0]["path"] if files else "",
        },
    }


def resolve_delivery_file(project_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("delivery path must stay inside the project")
    if not relative.parts or relative.parts[0] not in DELIVERY_ROOTS:
        raise ValueError("only exports and releases can be downloaded")
    target = (project_root / relative).resolve()
    if not target.is_relative_to(project_root.resolve()) or not target.is_file():
        raise FileNotFoundError(relative_path)
    if target.suffix.lower() not in DELIVERY_SUFFIXES:
        raise ValueError("this file type is not a user-facing delivery artifact")
    return target


def delivery_content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _delivery_files(project_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for folder_name in DELIVERY_ROOTS:
        folder = project_root / folder_name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in DELIVERY_SUFFIXES:
                continue
            if path.name.lower() in {"readme.md", "readme.txt", "placeholder.md", "placeholder.txt"}:
                continue
            stat = path.stat()
            relative = path.relative_to(project_root).as_posix()
            items.append(
                {
                    "id": relative,
                    "title": _display_title(path),
                    "path": relative,
                    "format": path.suffix.lower().lstrip(".").upper(),
                    "source": "正式发布" if folder_name == "releases" else "导出文件",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                }
            )
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return items


def _display_title(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ").strip()
    return title or path.name
