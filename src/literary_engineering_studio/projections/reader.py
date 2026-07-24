"""Read-only projection of formal prose for the ArcVellum reader."""

from __future__ import annotations

from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import quote

from literary_engineering_studio_engine.display_cleaner import (
    display_counts,
    markdown_to_display_text,
    scalar_from_yaml_text,
)
from literary_engineering_studio_engine.draft_text import final_body_from_workbench_text


READER_SCHEMA = "arcvellum/reader-manifest/v1"
_MANIFEST_CACHE: dict[str, tuple[str, dict[str, Any]]] = {}
_MANIFEST_LOCK = threading.RLock()


def build_reader_manifest(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    if not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"ArcVellum project not found: {root}")
    fingerprint = _project_fingerprint(root)
    cache_key = str(root)
    with _MANIFEST_LOCK:
        cached = _MANIFEST_CACHE.get(cache_key)
        if cached and cached[0] == fingerprint:
            return copy.deepcopy(cached[1])

    scenes = _scene_catalog(root)
    warnings: list[dict[str, str]] = []
    units: list[dict[str, Any]] = []
    covered_scenes: set[str] = set()

    for chapter_id in _chapter_ids(root, scenes):
        chapter_scenes = [item for item in scenes if item["chapter_id"] == chapter_id]
        chapter_unit, chapter_warnings = _best_chapter_unit(root, chapter_id, chapter_scenes)
        warnings.extend(chapter_warnings)
        if chapter_unit:
            units.append(chapter_unit)
            covered_scenes.update(str(item) for item in chapter_unit.get("coverage", []))

    for scene in scenes:
        scene_id = str(scene["scene_id"])
        if scene_id in covered_scenes:
            continue
        source = root / "drafts" / "scenes" / f"{scene_id}.md"
        if not source.is_file():
            continue
        body = _clean_body(source)
        if not body:
            continue
        units.append(
            _unit(
                root,
                unit_id=f"{scene['chapter_id']}.{scene_id}",
                volume_id=str(scene.get("volume_id") or ""),
                chapter_id=str(scene["chapter_id"]),
                scene_id=scene_id,
                order_key=tuple(scene["order_key"]),
                title=str(scene.get("title") or _human_scene_title(scene_id)),
                status="promoted",
                source_kind="scene",
                source=source,
                body=body,
                coverage=[scene_id],
            )
        )

    units.sort(key=lambda item: tuple(item.pop("_order_key")))
    for order, unit in enumerate(units, 1):
        unit["order"] = order
    revision_source = "\n".join(f"{unit['unit_id']}:{unit['content_hash']}" for unit in units)
    revision = hashlib.sha256(revision_source.encode("utf-8")).hexdigest()[:20]
    manifest = {
        "ok": True,
        "schema": READER_SCHEMA,
        "project_root": str(root),
        "project_revision": revision,
        "generated_at": _now(),
        "unit_count": len(units),
        "total_chinese_content_chars": sum(int(unit["chinese_content_chars"]) for unit in units),
        "units": units,
        "warnings": warnings,
    }
    with _MANIFEST_LOCK:
        _MANIFEST_CACHE[cache_key] = (fingerprint, copy.deepcopy(manifest))
    return manifest


def public_reader_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Remove internal file references from the browser-facing projection."""

    public = copy.deepcopy(manifest)
    for unit in public.get("units", []) if isinstance(public.get("units"), list) else []:
        if isinstance(unit, dict):
            unit.pop("source_path", None)
    return public


def read_reader_unit(project_root: Path, unit_id: str) -> dict[str, Any]:
    root = project_root.resolve()
    manifest = build_reader_manifest(root)
    unit = next((item for item in manifest["units"] if item.get("unit_id") == unit_id), None)
    if not unit:
        raise FileNotFoundError(f"reader unit not found: {unit_id}")
    source = _resolve_source(root, str(unit.get("source_path") or ""))
    body = _clean_body(source)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if digest != unit.get("content_hash"):
        raise RuntimeError("reader source changed while the unit was being loaded; refresh the manifest")
    public = {key: value for key, value in unit.items() if key != "source_path"}
    return {"ok": True, "schema": "arcvellum/reader-unit/v1", "unit": public, "body": body}


def search_reader(project_root: Path, query: str, *, limit: int = 40) -> dict[str, Any]:
    needle = query.strip().casefold()
    if not needle:
        return {"ok": True, "query": "", "items": []}
    manifest = build_reader_manifest(project_root)
    matches: list[dict[str, Any]] = []
    for unit in manifest["units"]:
        source = _resolve_source(project_root, str(unit.get("source_path") or ""))
        body = _clean_body(source)
        folded = body.casefold()
        cursor = folded.find(needle)
        if cursor < 0 and needle not in str(unit.get("title") or "").casefold():
            continue
        start = max(0, cursor - 70) if cursor >= 0 else 0
        end = min(len(body), (cursor + len(needle) + 110) if cursor >= 0 else 180)
        matches.append(
            {
                "unit_id": unit["unit_id"],
                "title": unit["title"],
                "order": unit["order"],
                "excerpt": re.sub(r"\s+", " ", body[start:end]).strip(),
            }
        )
        if len(matches) >= max(1, min(100, limit)):
            break
    return {"ok": True, "query": query.strip(), "items": matches}


def _scene_catalog(root: Path) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for fallback, path in enumerate(sorted((root / "scenes").glob("*.yaml")) if (root / "scenes").is_dir() else [], 1):
        text = path.read_text(encoding="utf-8", errors="ignore")
        scene_id = scalar_from_yaml_text(text, "scene_id") or path.stem
        chapter_id = scalar_from_yaml_text(text, "chapter_id") or "chapter_0001"
        volume_id = scalar_from_yaml_text(text, "volume_id")
        order = _first_int(text, ("scene_order", "sequence", "order"), fallback)
        chapter_order = _numeric_order(chapter_id, fallback)
        volume_order = _numeric_order(volume_id, 0)
        scenes.append(
            {
                "scene_id": scene_id,
                "chapter_id": chapter_id,
                "volume_id": volume_id,
                "title": scalar_from_yaml_text(text, "title"),
                "order_key": (volume_order, chapter_order, order, _numeric_order(scene_id, fallback)),
            }
        )
    scenes.sort(key=lambda item: tuple(item["order_key"]))
    return scenes


def _chapter_ids(root: Path, scenes: list[dict[str, Any]]) -> list[str]:
    ids = {str(item["chapter_id"]) for item in scenes}
    for folder in (root / "exports", root / "releases", root / "drafts" / "chapters"):
        if not folder.exists():
            continue
        if folder.name == "chapters":
            ids.update(path.stem for path in folder.glob("*.md"))
        else:
            ids.update(path.name for path in folder.iterdir() if path.is_dir())
    return sorted(ids, key=lambda value: (_numeric_order(value, 10**9), value))


def _best_chapter_unit(
    root: Path,
    chapter_id: str,
    scenes: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    expected = [str(item["scene_id"]) for item in scenes]
    candidates = _chapter_candidates(root, chapter_id)
    for status, kind, source, declared_coverage in candidates:
        coverage = declared_coverage or _chapter_workspace_coverage(root, chapter_id)
        if not coverage:
            warnings.append(
                {
                    "code": "coverage_missing",
                    "chapter_id": chapter_id,
                    "message": f"{chapter_id} 的{_source_label(kind)}没有声明场景覆盖范围，未用于覆盖逐场正文。",
                }
            )
            continue
        unknown = [scene_id for scene_id in coverage if expected and scene_id not in expected]
        if unknown:
            warnings.append(
                {
                    "code": "coverage_unknown_scene",
                    "chapter_id": chapter_id,
                    "message": f"{chapter_id} 的覆盖范围包含未知场景：{'、'.join(unknown[:5])}。",
                }
            )
            continue
        body = _clean_body(source)
        if not body:
            continue
        order_key = tuple(scenes[0]["order_key"]) if scenes else (0, _numeric_order(chapter_id, 10**9), 0, 0)
        return (
            _unit(
                root,
                unit_id=chapter_id,
                volume_id=str(scenes[0].get("volume_id") or "") if scenes else "",
                chapter_id=chapter_id,
                scene_id="",
                order_key=order_key,
                title=_first_heading(source) or _human_chapter_title(chapter_id),
                status=status,
                source_kind=kind,
                source=source,
                body=body,
                coverage=coverage,
            ),
            warnings,
        )
    return None, warnings


def _chapter_candidates(root: Path, chapter_id: str) -> list[tuple[str, str, Path, list[str]]]:
    result: list[tuple[str, str, Path, list[str]]] = []
    latest = _read_json(root / "releases" / chapter_id / "latest.json")
    manifest_rel = str(latest.get("manifest") or "")
    if manifest_rel:
        manifest = _read_json(_resolve_source(root, manifest_rel))
        outputs = manifest.get("published_outputs") if isinstance(manifest.get("published_outputs"), dict) else {}
        novel = str(outputs.get("novel") or "")
        if novel:
            result.append(("published", "release", _resolve_source(root, novel), _published_coverage(manifest)))
    export_manifest = _read_json(root / "exports" / chapter_id / "export_manifest.json")
    outputs = export_manifest.get("outputs") if isinstance(export_manifest.get("outputs"), dict) else {}
    novel = str(outputs.get("novel") or "")
    if novel:
        coverage = [str(item.get("scene_id")) for item in export_manifest.get("exported_scenes", []) if isinstance(item, dict) and item.get("scene_id")]
        result.append(("exported", "chapter", _resolve_source(root, novel), coverage))
    chapter = root / "drafts" / "chapters" / f"{chapter_id}.md"
    if chapter.is_file():
        result.append(("chapter", "chapter", chapter, _chapter_workspace_coverage(root, chapter_id)))
    return result


def _published_coverage(manifest: dict[str, Any]) -> list[str]:
    gates = manifest.get("gates") if isinstance(manifest.get("gates"), dict) else {}
    chapter = gates.get("chapter_workspace") if isinstance(gates.get("chapter_workspace"), dict) else {}
    json_path = str(chapter.get("json") or "")
    if not json_path:
        return []
    project_root = Path(str(manifest.get("project_root") or "."))
    payload = _read_json(_resolve_source(project_root, json_path))
    return [str(item.get("scene_id")) for item in payload.get("scenes", []) if isinstance(item, dict) and item.get("scene_id")]


def _chapter_workspace_coverage(root: Path, chapter_id: str) -> list[str]:
    payload = _read_json(root / "plot" / "chapters" / f"{chapter_id}.json")
    return [str(item.get("scene_id")) for item in payload.get("scenes", []) if isinstance(item, dict) and item.get("scene_id")]


def _unit(
    root: Path,
    *,
    unit_id: str,
    volume_id: str,
    chapter_id: str,
    scene_id: str,
    order_key: tuple[int, ...],
    title: str,
    status: str,
    source_kind: str,
    source: Path,
    body: str,
    coverage: list[str],
) -> dict[str, Any]:
    counts = display_counts(body)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    rel = source.resolve().relative_to(root.resolve()).as_posix()
    return {
        "unit_id": unit_id,
        "volume_id": volume_id,
        "chapter_id": chapter_id,
        "scene_id": scene_id,
        "order": 0,
        "title": title,
        "status": status,
        "source_kind": source_kind,
        "source_revision": f"{source.stat().st_mtime_ns:x}",
        "content_hash": digest,
        "chinese_content_chars": counts["chinese_content_chars"],
        "machine_nonspace_chars": counts["machine_nonspace_chars"],
        "coverage": coverage,
        "body_endpoint": f"/reader/units/{quote(unit_id, safe='')}",
        "source_path": rel,
        "_order_key": order_key,
    }


def _clean_body(path: Path) -> str:
    if not path.is_file():
        return ""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return markdown_to_display_text(final_body_from_workbench_text(raw), limit=0)


def _resolve_source(root: Path, value: str) -> Path:
    candidate = Path(value)
    path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("reader source escapes the project root") from exc
    return path


def _project_fingerprint(root: Path) -> str:
    parts: list[str] = []
    roots = [
        root / "project.yaml",
        root / "scenes",
        root / "drafts" / "scenes",
        root / "drafts" / "chapters",
        root / "exports",
        root / "releases",
        root / "plot" / "chapters",
    ]
    for candidate in roots:
        paths = [candidate] if candidate.is_file() else sorted(path for path in candidate.rglob("*") if path.is_file()) if candidate.is_dir() else []
        for path in paths:
            try:
                stat = path.stat()
                rel = path.resolve().relative_to(root).as_posix()
                parts.append(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}")
            except (OSError, ValueError):
                continue
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _first_int(text: str, keys: tuple[str, ...], fallback: int) -> int:
    for key in keys:
        value = scalar_from_yaml_text(text, key)
        if value:
            try:
                return int(value)
            except ValueError:
                pass
    return fallback


def _numeric_order(value: str, fallback: int) -> int:
    matches = re.findall(r"\d+", value or "")
    return int(matches[-1]) if matches else fallback


def _first_heading(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(r"(?m)^#{1,3}\s+(.+?)\s*$", path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1).strip() if match else ""


def _human_scene_title(scene_id: str) -> str:
    return f"场景 {_numeric_order(scene_id, 0):04d}" if _numeric_order(scene_id, 0) else scene_id


def _human_chapter_title(chapter_id: str) -> str:
    number = _numeric_order(chapter_id, 0)
    return f"第 {number} 章" if number else chapter_id


def _source_label(kind: str) -> str:
    return {"release": "发布稿", "chapter": "章节稿"}.get(kind, "正文")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
