"""Pure semantic contracts for Canon patches, lint, and lifecycle state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


CANON_PATCH_SCHEMA = "literary-engineering-workbench/canon-patch-candidate/v0.1"
CANON_PATCH_RISK_LEVELS = frozenset({"low", "medium", "high"})


class SceneLifecycleStatus(StrEnum):
    PLANNED = "planned"
    DRAFTING = "drafting"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"
    PUBLISHED = "published"


SCENE_LIFECYCLE_VALUES = tuple(status.value for status in SceneLifecycleStatus)
CHAPTER_SCENE_REQUIRED_FIELDS = ("scene_id", "path", "status")


@dataclass(frozen=True)
class CanonPatchCandidateIssue:
    """One machine-addressable Canon candidate contract violation."""

    path: str
    message: str


def canon_patch_candidate_issues(
    payload: dict[str, Any],
    *,
    expected_scene_id: str = "",
) -> tuple[CanonPatchCandidateIssue, ...]:
    """Validate Agent-owned Canon judgments without consulting project state."""

    issues: list[CanonPatchCandidateIssue] = []
    if payload.get("schema") != CANON_PATCH_SCHEMA:
        issues.append(CanonPatchCandidateIssue("schema", f"must equal {CANON_PATCH_SCHEMA}"))

    scene_id = str(payload.get("scene_id") or "").strip()
    if expected_scene_id and scene_id != expected_scene_id:
        issues.append(CanonPatchCandidateIssue("scene_id", f"must equal {expected_scene_id}"))

    canon_change = payload.get("canon_change")
    if not isinstance(canon_change, bool):
        issues.append(CanonPatchCandidateIssue("canon_change", "must be boolean"))

    items = payload.get("items")
    if not isinstance(items, list):
        issues.append(CanonPatchCandidateIssue("items", "must be a list"))
        items = []

    if canon_change is True and not items:
        issues.append(CanonPatchCandidateIssue("items", "must contain at least one durable fact when canon_change=true"))
    if canon_change is False:
        reason = str(payload.get("no_canon_change_reason") or "").strip()
        if not reason:
            issues.append(CanonPatchCandidateIssue("no_canon_change_reason", "is required when canon_change=false"))
        if items:
            issues.append(CanonPatchCandidateIssue("items", "must be empty when canon_change=false"))

    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            issues.append(CanonPatchCandidateIssue(prefix, "must be an object"))
            continue
        _validate_item(item, prefix, issues)
    return tuple(issues)


def _validate_item(
    item: dict[str, Any],
    prefix: str,
    issues: list[CanonPatchCandidateIssue],
) -> None:
    _require_text(item, "type", prefix, issues)
    _require_text(item, "summary", prefix, issues)
    _require_evidence(item, prefix, issues)
    _require_targets(item, prefix, issues)

    risk = str(item.get("risk_level") or "").strip().lower()
    if risk not in CANON_PATCH_RISK_LEVELS:
        issues.append(CanonPatchCandidateIssue(f"{prefix}.risk_level", "must be low, medium, or high"))
    if not isinstance(item.get("requires_user_approval"), bool):
        issues.append(CanonPatchCandidateIssue(f"{prefix}.requires_user_approval", "must be boolean"))


def _require_text(
    item: dict[str, Any],
    field: str,
    prefix: str,
    issues: list[CanonPatchCandidateIssue],
) -> None:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(CanonPatchCandidateIssue(f"{prefix}.{field}", "must be a non-empty string"))


def _require_evidence(
    item: dict[str, Any],
    prefix: str,
    issues: list[CanonPatchCandidateIssue],
) -> None:
    value = item.get("source_evidence")
    valid_text = isinstance(value, str) and bool(value.strip())
    valid_list = isinstance(value, list) and bool(value) and all(isinstance(row, str) and row.strip() for row in value)
    if not (valid_text or valid_list):
        issues.append(
            CanonPatchCandidateIssue(
                f"{prefix}.source_evidence",
                "must be a non-empty evidence locator or a non-empty list of evidence locators",
            )
        )


def _require_targets(
    item: dict[str, Any],
    prefix: str,
    issues: list[CanonPatchCandidateIssue],
) -> None:
    value = item.get("target_files")
    if not isinstance(value, list) or not value:
        issues.append(CanonPatchCandidateIssue(f"{prefix}.target_files", "must be a non-empty list"))
        return
    for target_index, target in enumerate(value):
        target_path = f"{prefix}.target_files[{target_index}]"
        if not isinstance(target, str) or not target.strip():
            issues.append(CanonPatchCandidateIssue(target_path, "must be a non-empty project-relative path"))
            continue
        if not _is_safe_canon_target(target):
            issues.append(CanonPatchCandidateIssue(target_path, "must be a project-relative path under canon/"))


def _is_safe_canon_target(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    return bool(
        normalized.startswith("canon/")
        and ".." not in parts
        and not Path(value).is_absolute()
        and not PureWindowsPath(value).is_absolute()
    )


__all__ = [
    "CANON_PATCH_RISK_LEVELS",
    "CANON_PATCH_SCHEMA",
    "CHAPTER_SCENE_REQUIRED_FIELDS",
    "SCENE_LIFECYCLE_VALUES",
    "CanonPatchCandidateIssue",
    "SceneLifecycleStatus",
    "canon_patch_candidate_issues",
]
