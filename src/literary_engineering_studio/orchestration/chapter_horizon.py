"""Deterministic chapter horizon projection and shadow evaluation (AO-5).

W6-6B projects chapter planning facts into a Rolling Horizon window plus
per-scene risk profiles, and exposes a measure-only shadow evaluation.  It
never executes a task, never persists, and never activates a plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping, Sequence

from .chapter_facts import (
    ChapterPlanningFacts,
    chapter_facts_violations,
    scene_order,
    scene_risk_values,
)
from .risk import (
    SceneRiskFacts,
    SceneRiskLevel,
    SceneRiskProfile,
    build_scene_risk_profile,
    scene_risk_violations,
)
from .rolling_horizon import (
    RollingHorizonWindow,
    build_rolling_horizon,
    rolling_horizon_violations,
)


@dataclass(frozen=True)
class ChapterHorizonViolation:
    code: str
    message: str


@dataclass(frozen=True)
class ChapterHorizonProjection:
    window: RollingHorizonWindow | None
    risk_profiles: tuple[SceneRiskProfile, ...]
    violations: tuple[ChapterHorizonViolation, ...]

    @property
    def passed(self) -> bool:
        return bool(self.window is not None and not self.violations)


@dataclass(frozen=True)
class ChapterHorizonShadowEvaluation:
    projection: ChapterHorizonProjection
    timing_ms: float
    executed: bool = False


def project_chapter_horizon(
    facts: ChapterPlanningFacts,
    *,
    active_scene_id: str,
    horizon_size: int,
    base_project_revision: str | None = None,
    rebase_after: Sequence[str] = (),
    proposed_levels: Mapping[str, SceneRiskLevel] | None = None,
) -> ChapterHorizonProjection:
    """Project planning facts into a horizon window and risk profiles."""
    violations = [
        ChapterHorizonViolation(item.code, item.message)
        for item in chapter_facts_violations(facts)
    ]
    if violations:
        return ChapterHorizonProjection(
            window=None,
            risk_profiles=(),
            violations=tuple(violations),
        )
    base_revision = (
        base_project_revision
        if base_project_revision is not None
        else facts.base_project_revision
    )
    try:
        window = build_rolling_horizon(
            chapter_id=facts.chapter_id,
            planned_scene_ids=scene_order(facts),
            active_scene_id=active_scene_id,
            horizon_size=horizon_size,
            base_project_revision=base_revision,
            rebase_after=rebase_after,
        )
    except ValueError as exc:
        return ChapterHorizonProjection(
            window=None,
            risk_profiles=(),
            violations=tuple(
                violations
                + [ChapterHorizonViolation(code="invalid-window", message=str(exc))]
            ),
        )
    violations.extend(
        ChapterHorizonViolation(item.code, item.message)
        for item in rolling_horizon_violations(window)
    )
    profiles = tuple(
        _profile_for_scene(
            scene,
            proposed_level=(
                proposed_levels.get(scene.scene_ref)
                if proposed_levels is not None
                else None
            ),
        )
        for scene in facts.scenes
    )
    for profile in profiles:
        violations.extend(
            ChapterHorizonViolation(item.code, item.message)
            for item in scene_risk_violations(_facts_for_profile(profile))
        )
    return ChapterHorizonProjection(
        window=window,
        risk_profiles=profiles,
        violations=tuple(dict.fromkeys(violations)),
    )


def evaluate_chapter_horizon_shadow(
    facts: ChapterPlanningFacts,
    *,
    active_scene_id: str,
    horizon_size: int,
    base_project_revision: str | None = None,
    rebase_after: Sequence[str] = (),
    proposed_levels: Mapping[str, SceneRiskLevel] | None = None,
) -> ChapterHorizonShadowEvaluation:
    """Measure-only shadow evaluation; never executes or persists."""
    started = perf_counter()
    projection = project_chapter_horizon(
        facts,
        active_scene_id=active_scene_id,
        horizon_size=horizon_size,
        base_project_revision=base_project_revision,
        rebase_after=rebase_after,
        proposed_levels=proposed_levels,
    )
    return ChapterHorizonShadowEvaluation(
        projection=projection,
        timing_ms=round(max(0.0, (perf_counter() - started) * 1000.0), 3),
    )


def _profile_for_scene(
    scene,
    *,
    proposed_level: SceneRiskLevel | None,
) -> SceneRiskProfile:
    facts = SceneRiskFacts(
        scene_id=scene.scene_ref,
        **dict(scene_risk_values(scene)),
    )
    return build_scene_risk_profile(facts, proposed_level=proposed_level)


def _facts_for_profile(profile: SceneRiskProfile) -> SceneRiskFacts:
    return SceneRiskFacts(
        scene_id=profile.scene_id,
        canon_change=profile.canon_change,
        character_state_change=profile.character_state_change,
        new_asset_risk=profile.new_asset_risk,
        branch_ambiguity=profile.branch_ambiguity,
        climax_weight=profile.climax_weight,
        continuity_debt=profile.continuity_debt,
        style_novelty=profile.style_novelty,
    )
