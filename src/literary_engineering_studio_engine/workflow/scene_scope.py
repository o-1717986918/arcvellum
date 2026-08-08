"""Shared scene-scope queries for workflow state and route audits."""
from __future__ import annotations

from pathlib import Path
import re


def started_scene_ids(root: Path) -> set[str]:
    """Return scene ids with durable evidence that formal work has started."""

    started: set[str] = set()
    _add_structured_scene_evidence(started, root)
    _add_candidate_scene_evidence(started, root)
    _add_branch_scene_evidence(started, root)
    _add_task_scene_evidence(started, root)
    return {scene_id for scene_id in started if scene_id.startswith("scene_")}


def _add_structured_scene_evidence(started: set[str], root: Path) -> None:
    for folder, pattern, transform in (
        (root / "memory" / "context_packets", "scene_*.md", lambda path: path.stem),
        (root / "drafts" / "compositions", "scene_*_composition.json", lambda path: path.stem.removesuffix("_composition")),
        (root / "reviews" / "agent", "scene_*_scene_review.json", lambda path: path.stem.removesuffix("_scene_review")),
        (root / "drafts" / "promotions", "scene_*_promotion.json", lambda path: path.stem.removesuffix("_promotion")),
        (root / "drafts" / "scenes", "scene_*.md", lambda path: path.stem),
        (root / "characters" / "state_patches", "scene_*_state_patch.json", lambda path: path.stem.removesuffix("_state_patch")),
    ):
        if folder.is_dir():
            started.update(transform(path) for path in folder.glob(pattern))


def _add_candidate_scene_evidence(started: set[str], root: Path) -> None:
    candidate_root = root / "drafts" / "candidates"
    if candidate_root.is_dir():
        for path in candidate_root.glob("scene_*.md"):
            scene_id = path.name.split("-", 1)[0]
            if scene_id.startswith("scene_"):
                started.add(scene_id)


def _add_branch_scene_evidence(started: set[str], root: Path) -> None:
    branch_root = root / "branches"
    if branch_root.is_dir():
        started.update(path.name for path in branch_root.iterdir() if path.is_dir() and path.name.startswith("scene_"))


def _add_task_scene_evidence(started: set[str], root: Path) -> None:
    task_root = root / "workflow" / "tasks"
    if task_root.is_dir():
        for path in task_root.glob("scene-development-scene_*-*.task.json"):
            match = re.match(r"scene-development-(scene_[^-]+)-", path.name)
            if match:
                started.add(match.group(1))
