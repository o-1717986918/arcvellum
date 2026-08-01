"""Chapter checkpoint contracts for AO-7 recovery (W6-8A).

A checkpoint captures the last formally verified safe state of a chapter.
Recovery may only restore a checkpoint whose base project fingerprint and
progress fingerprint still match the current project state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterCheckpoint:
    checkpoint_id: str
    chapter_id: str
    base_project_fingerprint: str
    progress_fingerprint: str
    last_task_id: str
    promoted_scene_ids: tuple[str, ...]
    pending_decision_ids: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class CheckpointViolation:
    code: str
    message: str


def checkpoint_violations(
    checkpoint: ChapterCheckpoint,
) -> tuple[CheckpointViolation, ...]:
    """Return deterministic structural violations for a checkpoint."""
    issues: list[CheckpointViolation] = []
    for name in (
        "checkpoint_id",
        "chapter_id",
        "base_project_fingerprint",
        "progress_fingerprint",
        "last_task_id",
        "created_at",
    ):
        if not getattr(checkpoint, name):
            issues.append(
                CheckpointViolation(
                    code="missing-field",
                    message=f"{name} must not be empty",
                )
            )
    promoted = checkpoint.promoted_scene_ids
    if len(set(promoted)) != len(promoted):
        issues.append(
            CheckpointViolation(
                code="duplicate-promoted-scene",
                message="promoted_scene_ids must not contain duplicates",
            )
        )
    return tuple(issues)


def checkpoint_matches(
    checkpoint: ChapterCheckpoint,
    *,
    base_project_fingerprint: str,
    progress_fingerprint: str,
) -> bool:
    """A checkpoint is restorable only when both identities still match."""
    return (
        checkpoint.base_project_fingerprint == base_project_fingerprint
        and checkpoint.progress_fingerprint == progress_fingerprint
    )


def checkpoint_newer(
    left: ChapterCheckpoint,
    right: ChapterCheckpoint,
) -> bool:
    """Deterministic ISO-8601 ordering; identical timestamps never win."""
    return left.created_at > right.created_at
