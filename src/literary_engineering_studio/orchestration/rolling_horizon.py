"""Deterministic chapter-level Rolling Horizon window contracts (AO-5).

The window describes which planned scenes receive deep roleplay/branch
planning.  It never creates tasks, never writes project facts, and never
changes the formal Engine lifecycle; it is a machine-owned projection that
later orchestration stages can consume in shadow or execution mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

MIN_HORIZON_SIZE = 2
MAX_HORIZON_SIZE = 4


@dataclass(frozen=True)
class RollingHorizonWindow:
    chapter_id: str
    planned_scene_ids: tuple[str, ...]
    deep_scene_ids: tuple[str, ...]
    active_scene_id: str
    horizon_size: int
    base_project_revision: str
    rebase_after: tuple[str, ...] = ()


@dataclass(frozen=True)
class RollingHorizonViolation:
    code: str
    message: str


def build_rolling_horizon(
    *,
    chapter_id: str,
    planned_scene_ids: Sequence[str],
    active_scene_id: str,
    horizon_size: int,
    base_project_revision: str,
    rebase_after: Sequence[str] = (),
    deep_scene_ids: Sequence[str] | None = None,
) -> RollingHorizonWindow:
    """Build a deterministic window for the scenes after the active scene.

    The deep window contains only future planned scenes (never the active
    scene itself) and is bounded by ``horizon_size``.  Near the end of a
    chapter the window may contain fewer scenes; it is empty only when no
    planned scene follows the active scene.
    """

    planned = tuple(planned_scene_ids)
    if not planned:
        raise ValueError("planned_scene_ids must not be empty")
    if active_scene_id not in planned:
        raise ValueError(f"active_scene_id is not in planned_scene_ids: {active_scene_id}")
    if not MIN_HORIZON_SIZE <= horizon_size <= MAX_HORIZON_SIZE:
        raise ValueError(
            f"horizon_size must be between {MIN_HORIZON_SIZE} and {MAX_HORIZON_SIZE}"
        )
    active_index = planned.index(active_scene_id)
    if deep_scene_ids is None:
        deep = planned[active_index + 1 : active_index + 1 + horizon_size]
    else:
        deep = tuple(deep_scene_ids)
    return RollingHorizonWindow(
        chapter_id=chapter_id,
        planned_scene_ids=planned,
        deep_scene_ids=deep,
        active_scene_id=active_scene_id,
        horizon_size=horizon_size,
        base_project_revision=base_project_revision,
        rebase_after=tuple(rebase_after),
    )


def rolling_horizon_violations(
    window: RollingHorizonWindow,
) -> tuple[RollingHorizonViolation, ...]:
    """Return deterministic cross-field violations for a window."""

    issues = _planned_scene_violations(window)
    if not issues and window.active_scene_id in window.planned_scene_ids:
        issues.extend(
            _deep_window_violations(
                window,
                active_index=window.planned_scene_ids.index(window.active_scene_id),
            )
        )
    return tuple(issues)


def _planned_scene_violations(
    window: RollingHorizonWindow,
) -> list[RollingHorizonViolation]:
    planned = window.planned_scene_ids
    issues: list[RollingHorizonViolation] = []
    if not planned:
        issues.append(
            RollingHorizonViolation(
                code="empty-planned-scenes",
                message="planned_scene_ids must not be empty",
            )
        )
        return issues
    if len(set(planned)) != len(planned):
        issues.append(
            RollingHorizonViolation(
                code="duplicate-planned-scenes",
                message="planned_scene_ids must not contain duplicates",
            )
        )
    if not MIN_HORIZON_SIZE <= window.horizon_size <= MAX_HORIZON_SIZE:
        issues.append(
            RollingHorizonViolation(
                code="horizon-size-out-of-range",
                message=(
                    f"horizon_size must be between {MIN_HORIZON_SIZE} "
                    f"and {MAX_HORIZON_SIZE}"
                ),
            )
        )
    if not window.base_project_revision:
        issues.append(
            RollingHorizonViolation(
                code="missing-base-revision",
                message="base_project_revision must not be empty",
            )
        )
    if window.active_scene_id not in planned:
        issues.append(
            RollingHorizonViolation(
                code="active-scene-not-planned",
                message=f"active_scene_id is not planned: {window.active_scene_id}",
            )
        )
        return issues
    return issues


def _deep_window_violations(
    window: RollingHorizonWindow,
    *,
    active_index: int,
) -> list[RollingHorizonViolation]:
    planned = window.planned_scene_ids
    deep = window.deep_scene_ids
    issues: list[RollingHorizonViolation] = []
    if len(set(deep)) != len(deep):
        issues.append(
            RollingHorizonViolation(
                code="duplicate-deep-scenes",
                message="deep_scene_ids must not contain duplicates",
            )
        )
    outside = [scene_id for scene_id in deep if scene_id not in planned]
    if outside:
        issues.append(
            RollingHorizonViolation(
                code="deep-scene-not-planned",
                message=f"deep scene is not planned: {outside[0]}",
            )
        )
    earlier = [
        scene_id
        for scene_id in deep
        if scene_id in planned and planned.index(scene_id) <= active_index
    ]
    if earlier:
        issues.append(
            RollingHorizonViolation(
                code="deep-scene-not-future",
                message=f"deep scene must follow the active scene: {earlier[0]}",
            )
        )
    if len(deep) > window.horizon_size:
        issues.append(
            RollingHorizonViolation(
                code="deep-scenes-exceed-horizon",
                message=(
                    f"deep window has {len(deep)} scenes, exceeding "
                    f"horizon_size {window.horizon_size}"
                ),
            )
        )
    remaining = len(planned) - active_index - 1
    if remaining > 0 and not deep:
        issues.append(
            RollingHorizonViolation(
                code="empty-deep-window",
                message=(
                    "deep window must not be empty while planned scenes "
                    "remain after the active scene"
                ),
            )
        )
    return issues
