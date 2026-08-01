"""Chapter-level AO-5 shadow evaluation (W6-6C).

This entry projects chapter planning facts onto a plan candidate and runs
the existing measure-only AO-2 pipeline.  It never executes a task, never
persists, and never activates a plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from .chapter_binding import (
    ChapterWindowPolicy,
    chapter_window_policy,
    project_chapter_candidate_parameters,
)
from .chapter_facts import ChapterPlanningFacts
from .chapter_facts_io import load_chapter_planning_facts
from .chapter_horizon import (
    ChapterHorizonViolation,
    project_chapter_horizon,
)
from .contracts import CompiledTaskGraph
from .risk import SceneRiskLevel, SceneRiskProfile
from .rolling_horizon import RollingHorizonWindow
from .shadow import ShadowPlanEvaluation, evaluate_shadow_candidate


@dataclass(frozen=True)
class ChapterPlanShadowEvaluation:
    window: RollingHorizonWindow | None
    risk_profiles: tuple[SceneRiskProfile, ...]
    policy: ChapterWindowPolicy | None
    plan_evaluation: ShadowPlanEvaluation | None
    violations: tuple[ChapterHorizonViolation, ...]
    timing_ms: float
    executed: bool = False

    @property
    def passed(self) -> bool:
        return bool(
            self.policy is not None
            and self.plan_evaluation is not None
            and self.plan_evaluation.passed
        )


def evaluate_chapter_plan_shadow(
    candidate_payload: dict[str, Any],
    *,
    facts: ChapterPlanningFacts,
    active_scene_id: str,
    horizon_size: int,
    base_project_revision: str | None = None,
    rebase_after: Sequence[str] = (),
    proposed_levels: Mapping[str, SceneRiskLevel] | None = None,
    normalization_context,
    lint_context,
    simulation_context_factory: Callable[[CompiledTaskGraph], Any],
) -> ChapterPlanShadowEvaluation:
    """Project chapter facts onto a candidate and evaluate in shadow mode."""
    started = perf_counter()
    projection = project_chapter_horizon(
        facts,
        active_scene_id=active_scene_id,
        horizon_size=horizon_size,
        base_project_revision=base_project_revision,
        rebase_after=rebase_after,
        proposed_levels=proposed_levels,
    )
    timing = _elapsed_ms(started)
    if not projection.passed or projection.window is None:
        return ChapterPlanShadowEvaluation(
            window=None,
            risk_profiles=projection.risk_profiles,
            policy=None,
            plan_evaluation=None,
            violations=projection.violations,
            timing_ms=timing,
        )
    policy = chapter_window_policy(projection.window, projection.risk_profiles)
    projected_payload, _ = project_chapter_candidate_parameters(
        candidate_payload,
        window=projection.window,
        profiles=projection.risk_profiles,
    )
    evaluation = evaluate_shadow_candidate(
        projected_payload,
        normalization_context=normalization_context,
        lint_context=lint_context,
        simulation_context_factory=simulation_context_factory,
    )
    return ChapterPlanShadowEvaluation(
        window=projection.window,
        risk_profiles=projection.risk_profiles,
        policy=policy,
        plan_evaluation=evaluation,
        violations=projection.violations,
        timing_ms=_elapsed_ms(started),
    )


def evaluate_chapter_plan_shadow_from_project(
    root: Path,
    chapter_id: str,
    candidate_payload: dict[str, Any],
    *,
    active_scene_id: str,
    horizon_size: int,
    base_project_revision: str = "",
    rebase_after: Sequence[str] = (),
    proposed_levels: Mapping[str, SceneRiskLevel] | None = None,
    normalization_context,
    lint_context,
    simulation_context_factory: Callable[[CompiledTaskGraph], Any],
) -> ChapterPlanShadowEvaluation:
    """Load project facts and evaluate the chapter plan in shadow mode."""
    facts = load_chapter_planning_facts(root, chapter_id)
    return evaluate_chapter_plan_shadow(
        candidate_payload,
        facts=facts,
        active_scene_id=active_scene_id,
        horizon_size=horizon_size,
        base_project_revision=base_project_revision or facts.base_project_revision,
        rebase_after=rebase_after,
        proposed_levels=proposed_levels,
        normalization_context=normalization_context,
        lint_context=lint_context,
        simulation_context_factory=simulation_context_factory,
    )


def _elapsed_ms(started: float) -> float:
    return round(max(0.0, (perf_counter() - started) * 1000.0), 3)
