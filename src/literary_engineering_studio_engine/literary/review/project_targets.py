"""Deterministic repair-target contracts for project-level reviews."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ALLOWED_PROJECT_REVIEW_TARGET_PREFIXES = (
    "canon/",
    "characters/",
    "plot/",
    "scenes/",
    "drafts/candidates/",
)
ALLOWED_PROJECT_REVIEW_TARGET_SUFFIXES = frozenset(
    {".md", ".json", ".yaml", ".yml", ".csv"}
)


@dataclass(frozen=True, slots=True)
class ProjectReviewTargetIssue:
    """One exact, user-repairable target-contract violation."""

    selector: str
    target: str
    message: str


def project_review_repair_target_issues(
    root: Path,
    payload: dict[str, object],
    fields: tuple[str, ...],
) -> list[ProjectReviewTargetIssue]:
    """Reject invented or unsafe targets before a review can schedule repair."""

    issues: list[ProjectReviewTargetIssue] = []
    for field in fields:
        items = payload.get(field) if isinstance(payload.get(field), list) else []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not _declares_repair(field, item):
                continue
            selector = f"{field}[{index}].target_path"
            target = _target_text(item)
            error = _target_error(root, target)
            if error:
                issues.append(ProjectReviewTargetIssue(selector, target, error))
    return issues


def valid_project_review_repair_targets(
    root: Path,
    payload: dict[str, object],
    fields: tuple[str, ...],
) -> list[str]:
    """Return unique existing repair targets from a validated review payload."""

    invalid = {
        issue.selector
        for issue in project_review_repair_target_issues(root, payload, fields)
    }
    targets: list[str] = []
    for field in fields:
        items = payload.get(field) if isinstance(payload.get(field), list) else []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not _declares_repair(field, item):
                continue
            if f"{field}[{index}].target_path" in invalid:
                continue
            target = _target_file(_target_text(item))
            if target and target not in targets:
                targets.append(target)
    return targets


def _declares_repair(field: str, item: dict[str, object]) -> bool:
    if field != "disagreements":
        return True
    return item.get("repair_required") is True or any(
        str(item.get(name) or "").strip()
        for name in ("target", "target_path", "action", "verification")
    )


def _target_text(item: dict[str, object]) -> str:
    return str(item.get("target_path") or item.get("target") or "").replace(
        "\\", "/"
    ).strip()


def _target_file(target: str) -> str:
    return target.split("#", 1)[0].strip()


def _target_error(root: Path, target: str) -> str:
    relative = _target_file(target)
    if not relative:
        return "repair target is missing"
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return f"repair target is not a safe project-relative path: {relative}"
    if not relative.startswith(ALLOWED_PROJECT_REVIEW_TARGET_PREFIXES):
        return f"repair target is outside the allowed project domains: {relative}"
    if path.suffix.lower() not in ALLOWED_PROJECT_REVIEW_TARGET_SUFFIXES:
        return f"repair target is not a supported text project file: {relative}"
    project_root = root.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError:
        return f"repair target resolves outside the work project: {relative}"
    if not candidate.is_file():
        return f"repair target does not exist in the work project: {relative}"
    return ""


__all__ = [
    "ProjectReviewTargetIssue",
    "project_review_repair_target_issues",
    "valid_project_review_repair_targets",
]
