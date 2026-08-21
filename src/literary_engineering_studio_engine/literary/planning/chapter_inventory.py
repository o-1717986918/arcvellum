"""Canonical chapter identity discovery for planning and delivery routes."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from ...foundation.display_cleaner import scalar_from_yaml_text


def formal_chapter_ids(project_root: Path) -> tuple[str, ...]:
    """Return chapter identities declared by creative assets, never derivatives."""

    root = project_root.resolve()
    scene_ids = _scene_chapter_ids(root)
    if scene_ids:
        return tuple(sorted(scene_ids, key=_natural_key))
    budget_ids = _budget_chapter_ids(root)
    if budget_ids:
        return tuple(sorted(budget_ids, key=_natural_key))
    workspace_ids = _self_consistent_workspace_ids(root)
    if workspace_ids:
        return tuple(sorted(workspace_ids, key=_natural_key))
    return ("chapter_0001",)


def formal_chapter_files(project_root: Path) -> tuple[Path, ...]:
    root = project_root.resolve()
    return tuple(
        path
        for chapter_id in formal_chapter_ids(root)
        if (path := root / "plot" / "chapters" / f"{chapter_id}.json").is_file()
    )


def is_final_chapter(project_root: Path, chapter_id: str) -> bool:
    ids = formal_chapter_ids(project_root)
    return bool(ids) and ids[-1] == chapter_id


def _scene_chapter_ids(root: Path) -> set[str]:
    scene_dir = root / "scenes"
    if not scene_dir.is_dir():
        return set()
    ids: set[str] = set()
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        chapter_id = scalar_from_yaml_text(
            path.read_text(encoding="utf-8"), "chapter_id"
        ).strip()
        if chapter_id and chapter_id != "unassigned":
            ids.add(chapter_id)
    return ids


def _budget_chapter_ids(root: Path) -> set[str]:
    payload = _read_json(root / "plot" / "word_budget" / "word_budget.json")
    rows = payload.get("chapter_budgets")
    if not isinstance(rows, list):
        return set()
    return {
        chapter_id
        for row in rows
        if isinstance(row, dict)
        if (chapter_id := str(row.get("chapter_id") or "").strip())
    }


def _self_consistent_workspace_ids(root: Path) -> set[str]:
    chapter_dir = root / "plot" / "chapters"
    if not chapter_dir.is_dir():
        return set()
    ids: set[str] = set()
    for path in sorted(chapter_dir.glob("*.json")):
        payload = _read_json(path)
        chapter_id = str(payload.get("chapter_id") or path.stem).strip()
        if not chapter_id or chapter_id != path.stem:
            continue
        scenes = payload.get("scenes")
        scene_chapters = {
            str(row.get("chapter_id") or "").strip()
            for row in scenes
            if isinstance(row, dict) and str(row.get("chapter_id") or "").strip()
        } if isinstance(scenes, list) else set()
        if not scene_chapters or scene_chapters == {chapter_id}:
            ids.add(chapter_id)
    return ids


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _natural_key(value: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    )


__all__ = ["formal_chapter_files", "formal_chapter_ids", "is_final_chapter"]
