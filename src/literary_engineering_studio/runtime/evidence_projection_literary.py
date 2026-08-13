"""Compact planning, scene, project, and style evidence for prose tasks."""

from __future__ import annotations


def prose_chapter_obligation(value: object) -> object:
    return _select_or_original(
        value,
        "schema", "chapter_id", "status", "count_unit", "target_chinese_chars",
        "scene_count_target", "chapter_function", "must_payoff", "must_setup", "must_change",
        "must_not_resolve", "inherited_hooks", "ending_hook", "inventory_sufficiency",
        "expansion_needed",
    )


def prose_word_budget(value: object, *, scene_id: str, chapter_id: str) -> object:
    if not isinstance(value, dict):
        return value
    binding = value.get("scene_inventory_binding")
    chapter_rows = binding.get("chapter_rows") if isinstance(binding, dict) else []
    chapter_id = chapter_id or _chapter_id_for_scene(scene_id, chapter_rows)
    return _select(value, "schema", "target", "totals") | {
        "current_chapter_budget": _matching_row(
            value.get("chapter_budgets"), "chapter_id", chapter_id
        ),
        "current_chapter_inventory": _planned_chapter_inventory(
            _matching_row(chapter_rows, "chapter_id", chapter_id)
        ),
    }


def prose_scene(value: object) -> object:
    return _select_or_original(
        value,
        "scene_id", "chapter_id", "chapter_obligation_id", "volume_id", "title",
        "word_count_target", "word_count_min", "word_count_max", "time", "location",
        "participants", "referenced_characters", "input_state", "scene_goal", "conflict",
        "actions", "revealed_info", "style_constraints", "reader_experience",
        "narrative_rhythm", "scene_bridge", "output_state", "next_hooks",
    )


def project_identity(value: object) -> object:
    return _select_or_original(value, "project", "creative_brief", "style")


def creative_quality(value: object) -> object:
    return _select_or_original(
        value,
        "schema", "profile_id", "name", "preset", "revision", "rule_modes", "thresholds",
        "punctuation", "custom_banned_phrases", "preferred_habits", "exceptions", "digest",
    )


def _planned_chapter_inventory(value: object) -> object:
    return _select_or_original(
        value, "chapter_id", "volume_id", "target_words", "target_scene_count", "avg_scene_words"
    )


def _chapter_id_for_scene(scene_id: str, rows: object) -> str:
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            scene_ids = row.get("scene_ids")
            if isinstance(scene_ids, list) and scene_id in scene_ids:
                return str(row.get("chapter_id") or "")
    return ""


def _matching_row(rows: object, key: str, expected: str) -> object:
    if not isinstance(rows, list):
        return {}
    if expected:
        for row in rows:
            if isinstance(row, dict) and str(row.get(key) or "") == expected:
                return row
    return rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}


def _select(value: dict, *keys: str) -> dict:
    return {key: value[key] for key in keys if key in value}


def _select_or_original(value: object, *keys: str) -> object:
    return _select(value, *keys) if isinstance(value, dict) else value


__all__ = [
    "creative_quality", "project_identity", "prose_chapter_obligation",
    "prose_scene", "prose_word_budget",
]
