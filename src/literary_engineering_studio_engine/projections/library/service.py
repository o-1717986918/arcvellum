"""Stable assembly of the complete read-only project-library snapshot."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import nested_scalar_from_yaml_text, read_jsonl_tail, scalar_from_yaml_text
from .assets import _branch_items, _character_items, _review_items, _scene_items, _style_items, _world_items
from .common import (
    PROJECT_LIBRARY_SCHEMA,
    _apply_overrides,
    _load_overrides,
    _now,
    _read_text,
    _with_key_points,
)
from .continuity import _canon_patch_items, _context_health_items, _continuity_items, _decision_items
from .drafts import _completed_prose_summary, _draft_items
from .story import _rhythm_items, _story_architecture_items, _word_budget_items

def build_project_library(project_root: Path) -> dict[str, object]:
    """Build a human-facing, read-only project library snapshot."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    overrides = _load_overrides(root)
    drafts = _draft_items(root, overrides)
    sections = {
        "drafts": drafts,
        "characters": _character_items(root, overrides),
        "world": _world_items(root, overrides),
        "scenes": _scene_items(root, overrides),
        "branches": _branch_items(root, overrides),
        "style": _style_items(root, overrides),
        "reviews": _review_items(root, overrides),
        "word_budget": _word_budget_items(root, overrides),
        "story_architecture": _story_architecture_items(root, overrides),
        "rhythm": _rhythm_items(root, overrides),
        "continuity": _continuity_items(root, overrides),
        "decisions": _decision_items(root, overrides),
        "context_health": _context_health_items(root, overrides),
        "canon_patches": _canon_patch_items(root, overrides),
    }
    sections = {key: [_with_key_points(item) for item in value] for key, value in sections.items()}
    counts = {key: len(value) for key, value in sections.items()}
    project = _project_card(root, overrides)
    return {
        "schema": PROJECT_LIBRARY_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "project": project,
        "counts": counts,
        "sections": sections,
        "completed_prose": _completed_prose_summary(drafts),
        "recent_human_choices": read_jsonl_tail(root / "workflow" / "human_choices" / "index.jsonl", 8),
        "recent_user_notes": read_jsonl_tail(root / "workflow" / "user_notes" / "index.jsonl", 8),
        "rules": [
            "This library is display-only. It packages artifacts for users but does not promote candidates or advance routes.",
            "Draft bodies are cleaned with final-delivery rules before display and counting.",
            "Canon, character, prose, and release changes must still use candidate/review/approval or formal CLI routes.",
        ],
    }

def find_project_library_item(project_root: Path, kind: str, item_id: str) -> dict[str, object]:
    library = build_project_library(project_root)
    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    items = sections.get(kind, []) if isinstance(sections, dict) else []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == item_id:
                return {"ok": True, "kind": kind, "item": item, "library_generated_at": library.get("generated_at", "")}
    raise FileNotFoundError(f"library item not found: {kind}/{item_id}")

def _project_card(root: Path, overrides: dict[str, object]) -> dict[str, object]:
    text = _read_text(root / "project.yaml")
    title = nested_scalar_from_yaml_text(text, "project", "title") or scalar_from_yaml_text(text, "title") or root.name
    project_type = nested_scalar_from_yaml_text(text, "project", "type") or "novel"
    target = nested_scalar_from_yaml_text(text, "project", "target_length") or nested_scalar_from_yaml_text(text, "longform_budget", "target_words")
    premise = nested_scalar_from_yaml_text(text, "creative_brief", "premise")
    genre = nested_scalar_from_yaml_text(text, "creative_brief", "genre")
    item = {
        "kind": "project",
        "id": "project",
        "title": title,
        "subtitle": "项目总览",
        "path": "project.yaml" if (root / "project.yaml").exists() else "",
        "status": nested_scalar_from_yaml_text(text, "project", "status") or "unknown",
        "badges": [badge for badge in [project_type, genre, f"目标 {target} 字" if target else ""] if badge],
        "excerpt": premise or "还没有项目简介。",
        "facts": [
            {"label": "作品类型", "value": project_type},
            {"label": "目标长度", "value": target or "未设置"},
            {"label": "语言", "value": nested_scalar_from_yaml_text(text, "project", "language") or "zh-CN"},
        ],
    }
    return _apply_overrides(item, overrides)
