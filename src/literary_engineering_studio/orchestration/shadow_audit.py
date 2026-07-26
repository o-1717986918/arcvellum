"""Machine-owned audit rendering for AO-3 shadow orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.foundation.atomic_io import (
    atomic_write_batch,
    atomic_write_text,
)

from .context_builder import AssembledPlanningContext
from .contracts import to_primitive
from .plan_events import CreativePlanEvent, CreativePlanEventType
from .planner import PlannerProtocolRun
from .reviewer import ReviewerProtocolRun
from .shadow import ShadowPlanEvaluation
from .shadow_run import (
    FixedRouteComparison,
    ShadowOrchestrationResult,
)


def write_shadow_evaluation(
    audit_root: Path,
    planner_run: PlannerProtocolRun,
    planning_context: AssembledPlanningContext,
    evaluation: ShadowPlanEvaluation,
    *,
    reviewer_run: ReviewerProtocolRun | None = None,
    review_context: AssembledPlanningContext | None = None,
    comparison: FixedRouteComparison | None = None,
) -> None:
    files = {
        audit_root / "candidate.completed.json": json_text(
            planner_run.completed_event.data["candidate"]
        ),
        audit_root / "normalized-plan.json": json_text(to_primitive(evaluation.plan)),
        audit_root / "lint.json": json_text(
            {
                "status": evaluation.lint_result.status,
                "digest": evaluation.lint_result.digest,
                "plan_digest": evaluation.lint_result.plan_digest,
                "issues": to_primitive(evaluation.lint_result.issues),
            }
        ),
        audit_root / "timing.json": json_text(to_primitive(evaluation.timing)),
        audit_root / "planner" / "context-ledger.json": json_text(
            planning_context.ledger.as_dict()
        ),
    }
    if evaluation.graph is not None:
        files[audit_root / "compiled-graph.json"] = json_text(
            to_primitive(evaluation.graph)
        )
    if evaluation.simulation is not None:
        files[audit_root / "simulation.json"] = json_text(
            to_primitive(evaluation.simulation)
        )
    if reviewer_run is not None:
        files[audit_root / "review.json"] = json_text(
            reviewer_run.receipt.as_dict()
        )
    if review_context is not None:
        files[audit_root / "reviewer" / "context-ledger.json"] = json_text(
            review_context.ledger.as_dict()
        )
    if comparison is not None:
        files[audit_root / "comparison.json"] = json_text(comparison.as_dict())
    atomic_write_batch(files)


def completed_comparison(
    *,
    fixed_steps: int,
    planner_run: PlannerProtocolRun,
    evaluation: ShadowPlanEvaluation,
    reviewer_run: ReviewerProtocolRun,
) -> FixedRouteComparison:
    assert evaluation.graph is not None and evaluation.simulation is not None
    return FixedRouteComparison(
        fixed_route_steps=fixed_steps,
        proposed_nodes=len(evaluation.graph.nodes),
        injected_gate_count=gate_count(evaluation),
        lint_status=evaluation.lint_result.status,
        simulation_status=evaluation.simulation.status,
        review_status=reviewer_run.receipt.verdict.value,
        planner_ms=planner_run.response.elapsed_ms,
        reviewer_ms=reviewer_run.response.elapsed_ms,
        deterministic_ms=evaluation.timing.total_ms,
    )


def record_fallback(
    operation_id: str,
    plan_id: str,
    audit_root: Path,
    reason: str,
    fixed_steps: int,
    detail: str = "",
    planner_session_id: str = "",
    reviewer_session_id: str = "",
    evaluation: ShadowPlanEvaluation | None = None,
    reviewer_run: ReviewerProtocolRun | None = None,
    events: list[CreativePlanEvent] | None = None,
) -> ShadowOrchestrationResult:
    event_list = list(events or ())
    event_list.append(
        fallback_event(
            plan_id,
            evaluation.plan.revision if evaluation is not None else 1,
            reviewer_session_id or planner_session_id or "machine-fixed-route",
            len(event_list),
            reason,
        )
    )
    comparison = FixedRouteComparison(
        fixed_route_steps=fixed_steps,
        proposed_nodes=len(evaluation.graph.nodes) if evaluation and evaluation.graph else 0,
        injected_gate_count=gate_count(evaluation),
        lint_status=evaluation.lint_result.status if evaluation else "not_run",
        simulation_status=(
            evaluation.simulation.status
            if evaluation and evaluation.simulation is not None
            else "not_run"
        ),
        review_status=(
            reviewer_run.receipt.verdict.value if reviewer_run is not None else "not_run"
        ),
        planner_ms=0.0,
        reviewer_ms=0.0,
        deterministic_ms=evaluation.timing.total_ms if evaluation else 0.0,
    )
    atomic_write_batch(
        {
            audit_root / "fallback.json": json_text(
                {
                    "schema": "arcvellum/orchestration-fallback/v1",
                    "status": "fixed_fallback",
                    "reason": reason,
                    "detail": detail,
                    "execution_route": "fixed",
                    "fixed_route_unchanged": True,
                }
            ),
            audit_root / "comparison.json": json_text(comparison.as_dict()),
            audit_root / "events.jsonl": events_text(event_list),
        }
    )
    return ShadowOrchestrationResult(
        operation_id=operation_id,
        plan_id=plan_id,
        status="fixed_fallback",
        execution_route="fixed",
        fallback_reason=reason,
        audit_root=audit_reference(audit_root),
        planner_session_id=planner_session_id,
        reviewer_session_id=reviewer_session_id,
        evaluation=evaluation,
        reviewer_run=reviewer_run,
        comparison=comparison,
        events=tuple(event_list),
    )


def gate_count(evaluation: ShadowPlanEvaluation | None) -> int:
    if evaluation is None:
        return 0
    return sum(
        len(binding.gate_ids)
        for binding in evaluation.plan.mandatory_gate_nodes
    )


def fallback_event(
    plan_id: str,
    revision: int,
    session_id: str,
    sequence: int,
    reason: str,
) -> CreativePlanEvent:
    return CreativePlanEvent(
        event_type=CreativePlanEventType.FALLBACK,
        plan_id=plan_id,
        revision=revision,
        session_id=session_id,
        sequence=sequence,
        data={"reason": reason, "execution_route": "fixed"},
    )


def write_events(path: Path, events: list[CreativePlanEvent]) -> None:
    atomic_write_text(path, events_text(events))


def events_text(events: list[CreativePlanEvent]) -> str:
    return "".join(
        json.dumps(event.as_dict(), ensure_ascii=False, sort_keys=True) + "\n"
        for event in events
    )


def write_json(path: Path, payload: dict[str, object]) -> None:
    atomic_write_text(path, json_text(payload))


def json_text(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def audit_reference(path: Path) -> str:
    parts = path.as_posix().split("/")
    try:
        index = parts.index("workflow")
    except ValueError:
        return path.name
    return "/".join(parts[index:])
