"""Pure validation rules for chapter and scene reader-experience contracts."""

from __future__ import annotations

from typing import Any, Iterable


def reader_contract_issues(
    payload: dict[str, Any],
    required_fields: Iterable[str],
) -> list[str]:
    if not payload:
        return ["reader experience contract missing for scene"]
    return [
        f"reader experience field missing: {field}"
        for field in required_fields
        if payload.get(field) in ("", None, [], {})
    ]


def chapter_scene_contract_issues(
    scenes: object,
    *,
    expected_scene_ids: tuple[str, ...],
    required_reader_fields: Iterable[str],
) -> list[str]:
    if not isinstance(scenes, list) or not scenes:
        return ["reader_experience_by_scene must contain at least one scene contract"]
    rows = [row for row in scenes if isinstance(row, dict)]
    issues = _scene_row_shape_issues(rows, scenes)
    actual_scene_ids = [str(row.get("scene_id") or "").strip() for row in rows]
    issues.extend(_scene_identity_issues(actual_scene_ids, expected_scene_ids))
    issues.extend(_scene_reader_issues(rows, required_reader_fields))
    return issues


def chapter_obligation_issues(
    payload: dict[str, Any],
    *,
    expected_scene_ids: tuple[str, ...],
    required_chapter_fields: Iterable[str],
    chapter_list_fields: Iterable[str],
    required_reader_fields: Iterable[str],
) -> list[str]:
    issues = [
        f"chapter obligation field missing: {field}"
        for field in required_chapter_fields
        if payload.get(field) in ("", None, [], {})
    ]
    issues.extend(
        f"chapter obligation field must be a list: {field}"
        for field in chapter_list_fields
        if not isinstance(payload.get(field), list)
    )
    issues.extend(
        chapter_scene_contract_issues(
            payload.get("reader_experience_by_scene"),
            expected_scene_ids=expected_scene_ids,
            required_reader_fields=required_reader_fields,
        )
    )
    return issues


def _scene_row_shape_issues(rows: list[dict[str, Any]], scenes: list[object]) -> list[str]:
    return [] if len(rows) == len(scenes) else ["reader_experience_by_scene entries must be objects"]


def _scene_identity_issues(
    actual_scene_ids: list[str],
    expected_scene_ids: tuple[str, ...],
) -> list[str]:
    issues: list[str] = []
    if len(actual_scene_ids) != len(set(actual_scene_ids)):
        issues.append("reader_experience_by_scene contains duplicate scene_id values")
    if expected_scene_ids and set(actual_scene_ids) != set(expected_scene_ids):
        missing = sorted(set(expected_scene_ids) - set(actual_scene_ids))
        extra = sorted(set(actual_scene_ids) - set(expected_scene_ids))
        issues.append(
            "reader_experience_by_scene must match the planned chapter scenes: "
            f"missing={missing or []}, extra={extra or []}"
        )
    return issues


def _scene_reader_issues(
    rows: list[dict[str, Any]],
    required_reader_fields: Iterable[str],
) -> list[str]:
    issues: list[str] = []
    for row in rows:
        scene_id = row.get("scene_id") or "unknown"
        issues.extend(
            f"reader experience {scene_id}: {message}"
            for message in reader_contract_issues(row, required_reader_fields)
        )
    return issues


__all__ = [
    "chapter_obligation_issues",
    "chapter_scene_contract_issues",
    "reader_contract_issues",
]
