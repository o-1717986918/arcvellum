"""Deterministic source contracts for formal export and publication."""

from __future__ import annotations

from pathlib import Path

from ..assets.canon.contracts import CANON_LINT_SOURCE_PATHS
from ..planning.chapter_inventory import formal_scene_ids_for_chapter
from ..scene.promotion.historical import historical_promotion_archive_paths


_CHAPTER_WORKSPACE_SOURCE_PATHS = (
    "project.yaml",
    "scenes",
    "memory/context_packets",
    "drafts/scenes",
    "drafts/candidates",
    "drafts/revisions",
    "drafts/promotions",
    "reviews",
    "branches",
    "drafts/compositions",
    "plot/word_budget",
    "plot/chapter_obligations",
    "plot/rhythm_plan.json",
    "plot/outline.md",
    "plot/conflict_matrix.md",
    "plot/foreshadowing.csv",
    "canon",
    "style",
    "characters",
)


def chapter_workspace_source_paths(
    project_root: Path,
    chapter_id: str,
) -> tuple[str, ...]:
    """Return current chapter inputs plus exact sealed scene archives."""

    return _with_historical_scene_archives(
        project_root,
        chapter_id,
        _CHAPTER_WORKSPACE_SOURCE_PATHS,
    )


def export_package_source_paths(
    project_root: Path,
    chapter_id: str,
) -> tuple[str, ...]:
    """Return package inputs plus the chapter's sealed readiness evidence."""

    return _with_historical_scene_archives(
        project_root,
        chapter_id,
        (
            f"plot/chapters/{chapter_id}.json",
            f"drafts/chapters/{chapter_id}.md",
            "drafts/scenes",
            "drafts/candidates",
            "drafts/revisions",
            "drafts/promotions",
            "reviews",
            "style",
        ),
    )


def _with_historical_scene_archives(
    project_root: Path,
    chapter_id: str,
    base_paths: tuple[str, ...],
) -> tuple[str, ...]:
    paths = list(base_paths)
    for scene_id in formal_scene_ids_for_chapter(project_root, chapter_id):
        paths.extend(historical_promotion_archive_paths(project_root, scene_id))
    return tuple(dict.fromkeys(paths))


def publish_chapter_source_paths(
    project_root: Path,
    chapter_id: str,
) -> tuple[str, ...]:
    """Return every project input read while publishing one chapter."""

    return _with_historical_scene_archives(
        project_root,
        chapter_id,
        (
            *CANON_LINT_SOURCE_PATHS,
            f"plot/chapters/{chapter_id}.json",
            f"drafts/chapters/{chapter_id}.md",
            "drafts/scenes",
            "drafts/candidates",
            "drafts/revisions",
            "drafts/promotions",
            "reviews",
            f"exports/{chapter_id}",
            "workflow/approvals/index.jsonl",
            "style",
        ),
    )


__all__ = [
    "chapter_workspace_source_paths",
    "export_package_source_paths",
    "publish_chapter_source_paths",
]
