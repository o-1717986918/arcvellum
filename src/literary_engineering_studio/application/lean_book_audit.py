"""Deterministic whole-book evidence for the lean creation route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    PLAN_SCHEMA,
    lean_scene_readiness,
    load_scene_facts,
    load_word_budget_summary,
)

from .chapter_checkpoint import checkpoint_revision_digest_from_revisions, checkpoint_path


def audit_lean_book(project_root: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    plan = _read(root / "plot" / "lean_project_plan.json")
    budget = _read(root / "plot" / "word_budget" / "word_budget.json")
    scenes, rows = _validated_inventory(root, plan, budget)
    chapter_sources = [
        _audit_chapter(root, data_root, row, scenes)
        for row in rows
    ]
    length_projection = _length_projection(root)
    return {
        "status": "pass",
        "blocking": "0",
        "literary_kernel": "lean-v2",
        "chapter_count": len(chapter_sources),
        "scene_count": len(scenes),
        "length_projection": length_projection,
        "chapters": chapter_sources,
    }


def _length_projection(root: Path) -> dict[str, Any]:
    budget = load_word_budget_summary(root, live=True)
    totals = budget.get("totals") if isinstance(budget.get("totals"), dict) else {}
    binding = budget.get("scene_inventory_binding") if isinstance(budget.get("scene_inventory_binding"), dict) else {}
    target = max(0, int(totals.get("target_words") or 0))
    actual = max(0, int(binding.get("actual_draft_chinese_chars") or 0))
    chapters = binding.get("chapter_rows") if isinstance(binding.get("chapter_rows"), list) else []
    return {
        "schema": "arcvellum/book-actuals/v1",
        "projection": "live-formal-scenes",
        "count_unit": "chinese_content_chars_including_chinese_punctuation",
        "target_chinese_content_chars": target,
        "actual_chinese_content_chars": actual,
        "completion_percent": round(actual * 100 / target, 2) if target else 0.0,
        "shortfall_chinese_content_chars": max(target - actual, 0),
        "chapter_actuals": [
            {
                "chapter_id": str(row.get("chapter_id") or ""),
                "target_chinese_content_chars": int(row.get("target_words") or 0),
                "actual_chinese_content_chars": int(row.get("actual_draft_chinese_chars") or 0),
                "scene_count": int(row.get("actual_scene_count") or 0),
            }
            for row in chapters
            if isinstance(row, dict)
        ],
    }


def _validated_inventory(
    root: Path, plan: dict[str, Any], budget: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("lean project plan is missing or invalid")
    chapters, scenes, rows = _inventory_lists(plan, budget)
    if len(chapters) != len(rows) or len(scenes) != sum(int(row["scene_count"]) for row in rows):
        raise ValueError("lean scene inventory does not cover the word budget")
    expected_chapters = [str(row["chapter_id"]) for row in rows]
    if [str(item.get("chapter_id")) for item in chapters] != expected_chapters:
        raise ValueError("lean chapter spine differs from the word budget")
    ids = [str(scene.get("scene_id")) for scene in scenes]
    if ids != [f"scene_{index:04d}" for index in range(1, len(scenes) + 1)]:
        raise ValueError("lean scene IDs are not contiguous")
    _validate_scene_files(root, ids)
    return scenes, rows


def _inventory_lists(
    plan: dict[str, Any], budget: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    values = (plan.get("chapters"), plan.get("scenes"), budget.get("chapter_budgets"))
    if any(not isinstance(value, list) for value in values):
        raise ValueError("lean plan and word budget are incomplete")
    return values  # type: ignore[return-value]


def _validate_scene_files(root: Path, ids: list[str]) -> None:
    expected_files = {f"{scene_id}.yaml" for scene_id in ids}
    existing_files = {path.name for path in (root / "scenes").glob("scene_*.yaml")}
    if existing_files != expected_files:
        raise ValueError("formal scene files differ from the lean plan")


def _audit_chapter(
    root: Path, data_root: Path, row: dict[str, Any], scenes: list[dict[str, Any]]
) -> tuple[str, tuple[Path, ...]]:
    chapter_id = str(row["chapter_id"])
    chapter_scenes = [scene for scene in scenes if scene.get("chapter_id") == chapter_id]
    if len(chapter_scenes) != int(row["scene_count"]):
        raise ValueError(f"scene count differs for {chapter_id}")
    audited = [_audit_scene(root, chapter_id, scene) for scene in chapter_scenes]
    receipts = [revision for revision, _path in audited]
    checkpoint = _read(checkpoint_path(data_root, root, chapter_id))
    digest = checkpoint_revision_digest_from_revisions(receipts)
    if checkpoint.get("committed_revision_digest") != digest or checkpoint.get("status") not in {"pass", "needs-attention"}:
        raise ValueError(f"chapter checkpoint is missing, stale or blocked: {chapter_id}")
    return chapter_id, tuple(path for _revision, path in audited)


def _audit_scene(root: Path, chapter_id: str, scene: dict[str, Any]) -> tuple[str, Path]:
    scene_id = str(scene["scene_id"])
    facts = load_scene_facts(root / "scenes" / f"{scene_id}.yaml")
    if facts.scene_id != scene_id or facts.chapter_id != chapter_id:
        raise ValueError(f"formal scene identity differs: {scene_id}")
    readiness = lean_scene_readiness(root, scene_id)
    if readiness is None or readiness[0] != "ready":
        raise ValueError(f"scene has no passing lean commit: {scene_id}")
    receipt = _read(root / "workflow" / "scene_commits" / f"{scene_id}.json")
    delta = root / "workflow" / "scene_deltas" / f"{scene_id}.json"
    if not delta.is_file() or not _delta_matches(delta, receipt):
        raise ValueError(f"scene delta is missing or changed: {scene_id}")
    revision = str(receipt.get("committed_revision") or "")
    if len(revision) != 64:
        raise ValueError(f"scene commit revision is missing: {scene_id}")
    return revision, root / "drafts" / "scenes" / f"{scene_id}.md"


def _delta_matches(path: Path, receipt: dict[str, Any]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest() == receipt.get("delta_sha256")


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


__all__ = ["audit_lean_book"]
