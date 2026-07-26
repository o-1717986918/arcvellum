"""Measure-only AO-2 pipeline that cannot execute or activate a plan."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from .candidate import parse_plan_candidate
from .compiler import compile_plan
from .contracts import CompiledTaskGraph, CreativeExecutionPlan
from .lint import PlanLintContext, PlanLintResult, lint_plan
from .normalizer import NormalizationContext, normalize_plan_candidate
from .plan_events import CreativePlanEvent, completed_candidate_from_event
from .simulator import PlanSimulationContext, PlanSimulationResult, simulate_plan


@dataclass(frozen=True)
class ShadowStageTiming:
    normalize_ms: float
    lint_ms: float
    compile_ms: float
    simulate_ms: float
    total_ms: float


@dataclass(frozen=True)
class ShadowPlanEvaluation:
    plan: CreativeExecutionPlan
    lint_result: PlanLintResult
    graph: CompiledTaskGraph | None
    simulation: PlanSimulationResult | None
    timing: ShadowStageTiming

    @property
    def passed(self) -> bool:
        return bool(
            self.lint_result.passed
            and self.graph is not None
            and self.simulation is not None
            and self.simulation.passed
        )


def evaluate_shadow_candidate(
    candidate_payload: dict[str, Any],
    *,
    normalization_context: NormalizationContext,
    lint_context: PlanLintContext,
    simulation_context_factory: Callable[[CompiledTaskGraph], PlanSimulationContext],
) -> ShadowPlanEvaluation:
    started = perf_counter()
    stage = perf_counter()
    parsed = parse_plan_candidate(candidate_payload)
    plan = normalize_plan_candidate(parsed, context=normalization_context)
    normalize_ms = _elapsed_ms(stage)

    stage = perf_counter()
    lint_result = lint_plan(plan, context=lint_context)
    lint_ms = _elapsed_ms(stage)
    if not lint_result.passed:
        return ShadowPlanEvaluation(
            plan=plan,
            lint_result=lint_result,
            graph=None,
            simulation=None,
            timing=ShadowStageTiming(
                normalize_ms=normalize_ms,
                lint_ms=lint_ms,
                compile_ms=0.0,
                simulate_ms=0.0,
                total_ms=_elapsed_ms(started),
            ),
        )

    stage = perf_counter()
    graph = compile_plan(plan, lint_result=lint_result)
    compile_ms = _elapsed_ms(stage)

    stage = perf_counter()
    simulation = simulate_plan(graph, context=simulation_context_factory(graph))
    simulate_ms = _elapsed_ms(stage)
    return ShadowPlanEvaluation(
        plan=plan,
        lint_result=lint_result,
        graph=graph,
        simulation=simulation,
        timing=ShadowStageTiming(
            normalize_ms=normalize_ms,
            lint_ms=lint_ms,
            compile_ms=compile_ms,
            simulate_ms=simulate_ms,
            total_ms=_elapsed_ms(started),
        ),
    )


def evaluate_completed_shadow_candidate(
    event: CreativePlanEvent,
    *,
    normalization_context: NormalizationContext,
    lint_context: PlanLintContext,
    simulation_context_factory: Callable[[CompiledTaskGraph], PlanSimulationContext],
) -> ShadowPlanEvaluation:
    """Cross the Planner/Lint boundary only after a typed completion event."""

    return evaluate_shadow_candidate(
        completed_candidate_from_event(event),
        normalization_context=normalization_context,
        lint_context=lint_context,
        simulation_context_factory=simulation_context_factory,
    )


def _elapsed_ms(started: float) -> float:
    return round(max(0.0, (perf_counter() - started) * 1000.0), 3)
