"""Read-only Style Atelier application service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from literary_engineering_studio_engine.style_lab import (
    active_project_style,
    default_style_library_root,
)

from .contracts import RightsProjection, SourceProjection
from .version_service import StyleVersionProjectionService


class StyleApplicationService:
    def __init__(self, versions: StyleVersionProjectionService | None = None):
        self.versions = versions or StyleVersionProjectionService()

    def authors(self, library_root: Path | None = None) -> dict[str, object]:
        root = self._library_root(library_root)
        items, issues = self._project_authors(root)
        return {
            "schema": "arcvellum/style-author-catalog/v1",
            "authors": items,
            "count": len(items),
            "issues": issues,
        }

    def version_catalog(
        self,
        library_root: Path | None = None,
        *,
        project_root: Path | None = None,
    ) -> dict[str, object]:
        root = self._library_root(library_root)
        active = active_project_style(project_root) if project_root is not None else {}
        active_style_id = str(active.get("style_id") or "")
        active_hash = str(active.get("content_hash") or active.get("version_hash") or "")
        versions: list[dict[str, object]] = []
        issues: list[str] = []
        for author_dir in self._author_dirs(root):
            projected, author_issues = self.versions.project_author_versions(
                root,
                author_dir,
                active_style_id=active_style_id,
                active_content_hash=active_hash,
            )
            versions.extend(projected)
            issues.extend(author_issues)
        revision = _json_hash({"versions": versions, "active": _safe_active_mount(active)})
        return {
            "schema": "arcvellum/style-version-catalog/v1",
            "revision": revision,
            "versions": versions,
            "count": len(versions),
            "active_mount": _safe_active_mount(active),
            "issues": issues,
        }

    def _project_authors(self, root: Path) -> tuple[list[dict[str, object]], list[str]]:
        authors: list[dict[str, object]] = []
        issues: list[str] = []
        for author_dir in self._author_dirs(root):
            manifest = _read_json(author_dir / "author.json")
            if not manifest:
                issues.append(f"invalid author manifest: {author_dir.name}")
                continue
            rights = RightsProjection(
                mode=str(manifest.get("mode") or ""),
                declaration=str(manifest.get("source_note") or ""),
            )
            works = [
                work
                for work_dir in sorted((author_dir / "works").glob("*"))
                if work_dir.is_dir() and (work := _project_work(root, work_dir))
            ]
            authors.append(
                {
                    "author_id": str(manifest.get("author_id") or author_dir.name),
                    "name": str(manifest.get("name") or author_dir.name),
                    "rights": rights.as_dict(),
                    "updated_at": str(manifest.get("updated_at") or ""),
                    "works": works,
                    "work_count": len(works),
                    "profile_count": len([path for path in (author_dir / "profiles").glob("*") if path.is_dir()]),
                    "style_skill_count": len(
                        [path for path in (author_dir / "style_skills").glob("*/style_skill.json") if path.is_file()]
                    ),
                }
            )
        return authors, issues

    @staticmethod
    def _library_root(library_root: Path | None) -> Path:
        root = (library_root or default_style_library_root()).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"style library root not found: {root}")
        return root

    @staticmethod
    def _author_dirs(root: Path) -> list[Path]:
        return [
            path.parent
            for path in sorted((root / "authors").glob("*/author.json"))
            if path.is_file() and _inside(root, path)
        ]


def _project_work(root: Path, work_dir: Path) -> dict[str, object] | None:
    manifest = _read_json(work_dir / "work.json")
    if not manifest or not _inside(root, work_dir):
        return None
    sources = _project_sources(work_dir)
    return {
        "work_id": str(manifest.get("work_id") or work_dir.name),
        "title": str(manifest.get("title") or work_dir.name),
        "year": str(manifest.get("year") or ""),
        "notes": str(manifest.get("notes") or ""),
        "sources": sources,
        "source_count": len(sources),
    }


def _project_sources(work_dir: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for source_manifest in sorted((work_dir / "sources").glob("*.source.json")):
        item = _project_source(work_dir, source_manifest)
        if item is not None:
            items.append(item)
    return items


def _project_source(work_dir: Path, source_manifest: Path) -> dict[str, object] | None:
    payload = _read_json(source_manifest)
    normalized = _resolve_relative(work_dir, str(payload.get("normalized") or ""))
    if not payload or normalized is None or not normalized.is_file():
        return None
    return SourceProjection(
        source_id=str(payload.get("source_id") or source_manifest.stem),
        filename=str(payload.get("filename") or ""),
        content_sha256=hashlib.sha256(normalized.read_bytes()).hexdigest(),
        character_count=int(payload.get("char_count") or 0),
        chunk_count=int(payload.get("chunk_count") or 0),
        imported_at=str(payload.get("imported_at") or ""),
    ).as_dict()


def _safe_active_mount(payload: dict[str, object]) -> dict[str, object]:
    allowed = {
        "schema",
        "style_id",
        "author",
        "author_id",
        "profile_id",
        "priority",
        "mounted_at",
        "readiness",
        "enforcement",
        "content_hash",
        "version_hash",
    }
    return {key: payload[key] for key in allowed if key in payload}


def _resolve_relative(root: Path, relative: str) -> Path | None:
    if not relative:
        return None
    target = (root / relative).resolve()
    return target if _inside(root, target) else None


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _json_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
