"""Chapter checkpoint contracts for AO-7 recovery (W6-8A).

A checkpoint captures the last formally verified safe state of a chapter.
Recovery may only restore a checkpoint whose base project fingerprint and
progress fingerprint still match the current project state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..protocols.violations import ContractViolation


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


CheckpointViolation = ContractViolation


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
    if checkpoint.created_at:
        try:
            _created_at_in_utc(checkpoint.created_at)
        except ValueError as exc:
            issues.append(
                CheckpointViolation(
                    code="invalid-created-at",
                    message=str(exc),
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
    """Compare timezone-aware instants; identical timestamps never win."""
    return _created_at_in_utc(left.created_at) > _created_at_in_utc(
        right.created_at
    )


def _created_at_in_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("created_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must include a timezone offset")
    return parsed.astimezone(timezone.utc)
