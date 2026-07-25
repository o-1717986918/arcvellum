"""Bounded impact preview for Archive mutations."""

from __future__ import annotations

from pathlib import Path

from .contracts import AssetRecord


_TEXT_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml", ".csv"}
_SEARCH_ROOTS = ("characters", "scenes", "canon", "plot", "memory", "drafts", "reviews", "workflow")


def build_asset_impact(project_root: Path, asset: AssetRecord, replacement_content: str) -> dict[str, object]:
    changed = replacement_content != asset.content
    references: list[dict[str, str]] = []
    if changed:
        references = _reference_paths(project_root, asset)
    categories = sorted({str(item["category"]) for item in references})
    return {
        "schema": "arcvellum/archive-impact/v1",
        "asset_id": asset.asset_id,
        "changed": changed,
        "summary": "需要重新核对受影响资料。" if references else "没有发现直接文本引用。",
        "reference_count": len(references),
        "references": references,
        "stale_categories": categories,
    }


def _reference_paths(root: Path, asset: AssetRecord) -> list[dict[str, str]]:
    needles = {asset.asset_id, asset.local_id, asset.relative_path}
    found: list[dict[str, str]] = []
    for folder_name in _SEARCH_ROOTS:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            if relative == asset.relative_path or relative.startswith("workflow/archive/"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not any(needle and needle in text for needle in needles):
                continue
            found.append({"path": relative, "category": _impact_category(relative)})
            if len(found) >= 500:
                return found
    return found


def _impact_category(relative: str) -> str:
    if relative.startswith("memory/context_packets/"):
        return "context"
    if "composition" in relative:
        return "composition"
    if relative.startswith("reviews/"):
        return "review"
    if "promotion" in relative:
        return "promotion"
    if relative.startswith(("scenes/", "plot/")):
        return "planning"
    return "project-reference"
