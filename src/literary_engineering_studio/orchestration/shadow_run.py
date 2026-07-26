"""Public AO-3 shadow-run inputs, results, and comparison evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .context_builder import PlanningSourceDocument
from .contracts import CompiledTaskGraph
from .lint import PlanLintContext
from .normalizer import NormalizationContext
from .persistence import OrchestrationAuditArtifacts
from .plan_events import CreativePlanEvent
from .plan_index import CreativePlanIndex
from .reviewer import ReviewerProtocolRun
from .shadow import ShadowPlanEvaluation
from .simulator import PlanSimulationContext


@dataclass(frozen=True)
class FixedRouteComparison:
    fixed_route_steps: int
    proposed_nodes: int
    injected_gate_count: int
    lint_status: str
    simulation_status: str
    review_status: str
    planner_ms: float
    reviewer_ms: float
    deterministic_ms: float
    fixed_route_unchanged: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "arcvellum/orchestration-shadow-comparison/v1",
            "fixed_route_steps": self.fixed_route_steps,
            "proposed_nodes": self.proposed_nodes,
            "injected_gate_count": self.injected_gate_count,
            "lint_status": self.lint_status,
            "simulation_status": self.simulation_status,
            "review_status": self.review_status,
            "planner_ms": self.planner_ms,
            "reviewer_ms": self.reviewer_ms,
            "deterministic_ms": self.deterministic_ms,
            "fixed_route_unchanged": self.fixed_route_unchanged,
        }


@dataclass(frozen=True)
class ShadowOrchestrationResult:
    operation_id: str
    plan_id: str
    status: str
    execution_route: str
    fallback_reason: str
    audit_root: str
    planner_session_id: str = ""
    reviewer_session_id: str = ""
    evaluation: ShadowPlanEvaluation | None = None
    reviewer_run: ReviewerProtocolRun | None = None
    artifacts: OrchestrationAuditArtifacts | None = None
    comparison: FixedRouteComparison | None = None
    events: tuple[CreativePlanEvent, ...] = ()

    @property
    def shadow_completed(self) -> bool:
        return self.status == "shadow_completed"


@dataclass(frozen=True)
class ShadowPlanningInput:
    project_root: Path
    objective: str
    sources: tuple[PlanningSourceDocument, ...]
    normalization_context: NormalizationContext
    lint_context: PlanLintContext
    simulation_context_factory: Callable[[CompiledTaskGraph], PlanSimulationContext]
    fingerprint_provider: Callable[[], str]
    store: CreativePlanIndex | None = None
