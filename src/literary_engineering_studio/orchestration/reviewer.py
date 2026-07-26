"""Independent semantic review for one exact compiled orchestration plan."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .agent_protocol import (
    OrchestrationAgentRequest,
    OrchestrationReviewReceipt,
    parse_review_judgment,
    seal_orchestration_review,
)
from .agent_transport import (
    OrchestrationAgentResponse,
    OrchestrationAgentTransport,
)
from .audit_integrity import canonical_json_digest
from .context_builder import (
    AssembledPlanningContext,
    PlanningSourceDocument,
    assemble_planning_context,
)
from .contracts import CompiledTaskGraph, CreativeExecutionPlan, to_primitive
from .lint import PlanLintResult
from .profiles import OrchestrationAgentRole
from .simulator import PlanSimulationResult
from .truth_partition import TruthPartition

if TYPE_CHECKING:
    from .planner import PlannerProtocolRun
    from .shadow import ShadowPlanEvaluation


@dataclass(frozen=True)
class ReviewerProtocolRun:
    response: OrchestrationAgentResponse
    request: OrchestrationAgentRequest
    receipt: OrchestrationReviewReceipt


def run_reviewer(
    transport: OrchestrationAgentTransport,
    *,
    planner_session_id: str,
    logical_session_id: str,
    context: AssembledPlanningContext,
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
    audit_root: Path,
) -> ReviewerProtocolRun:
    subject_digests = (
        plan.candidate_digest,
        lint_result.plan_digest,
        graph.graph_digest,
        canonical_json_digest(to_primitive(simulation)),
    )
    request = OrchestrationAgentRequest(
        request_id=f"{plan.plan_id}:reviewer:{plan.revision}",
        session_id=logical_session_id,
        role=OrchestrationAgentRole.REVIEWER,
        objective="Critically review the exact plan and deterministic evidence.",
        context_ledger_id=context.ledger.ledger_id,
        context_ledger_digest=context.ledger.digest,
        subject_digests=subject_digests,
    )
    response = transport.invoke(
        OrchestrationAgentRole.REVIEWER,
        prompt=_reviewer_prompt(request, context),
        audit_root=audit_root,
    )
    if not response.session_id:
        raise RuntimeError("Reviewer runtime did not return an actual session identity")
    receipt = seal_orchestration_review(
        parse_review_judgment(response.payload),
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        planner_session_id=planner_session_id,
        reviewer_session_id=response.session_id,
        context_ledger_digest=context.ledger.digest,
        candidate_digest=plan.candidate_digest,
        plan_digest=lint_result.plan_digest,
        graph_digest=graph.graph_digest,
        simulation_digest=subject_digests[-1],
    )
    return ReviewerProtocolRun(response=response, request=request, receipt=receipt)


def _reviewer_prompt(
    request: OrchestrationAgentRequest,
    context: AssembledPlanningContext,
) -> str:
    return "\n\n".join(
        (
            "# ArcVellum Independent Orchestration Review",
            "Return exactly one JSON object and no commentary or Markdown fence.",
            "Review the exact candidate and machine evidence below. Do not rewrite the plan, activate it, "
            "or excuse missing literary obligations for speed. A fail verdict must include an error finding.",
            "## Machine request\n" + json.dumps(request.as_dict(), ensure_ascii=False, indent=2),
            "## Exact review context\n" + context.text,
        )
    )


def assemble_reviewer_context(
    *,
    project_root_hash: str,
    operation_id: str,
    logical_session_id: str,
    plan_id: str,
    planner_context: AssembledPlanningContext,
    planner_run: PlannerProtocolRun,
    evaluation: ShadowPlanEvaluation,
) -> AssembledPlanningContext:
    """Build the exact bounded evidence packet consumed by the Reviewer."""

    sources = _review_sources(planner_context, planner_run, evaluation)
    total_characters = sum(len(source.content) for source in sources)
    if total_characters > 180_000:
        raise ValueError("exact Reviewer evidence exceeds the bounded context budget")
    context = assemble_planning_context(
        sources,
        project_root_hash=project_root_hash,
        session_id=logical_session_id,
        operation_id=operation_id + ":review",
        plan_id=plan_id,
        max_source_characters=max(len(source.content) for source in sources),
        max_total_characters=total_characters,
    )
    if any(entry.truncated or not entry.included for entry in context.ledger.entries):
        raise RuntimeError("exact Reviewer evidence was unexpectedly truncated")
    return context


def _review_sources(
    planner_context: AssembledPlanningContext,
    planner_run: PlannerProtocolRun,
    evaluation: ShadowPlanEvaluation,
) -> tuple[PlanningSourceDocument, ...]:
    assert evaluation.graph is not None and evaluation.simulation is not None
    return (
        PlanningSourceDocument(
            "orchestration/planner-context-ledger.json",
            "Planner context ledger",
            "prove what the Planner received",
            TruthPartition.EVIDENCE,
            _json_text(planner_context.ledger.as_dict()),
            mandatory=True,
        ),
        PlanningSourceDocument(
            "orchestration/candidate.json",
            "Exact plan candidate",
            "review the model-authored proposal",
            TruthPartition.FUTURE_INTENT,
            _json_text(planner_run.completed_event.data["candidate"]),
            mandatory=True,
        ),
        PlanningSourceDocument(
            "orchestration/normalized-plan.json",
            "Machine-normalized plan",
            "review the sealed machine fields and gate bindings",
            TruthPartition.FUTURE_INTENT,
            _json_text(to_primitive(evaluation.plan)),
            mandatory=True,
        ),
        PlanningSourceDocument(
            "orchestration/lint.json",
            "Plan Lint evidence",
            "inspect deterministic plan validity",
            TruthPartition.EVIDENCE,
            _json_text(
                {
                    "status": evaluation.lint_result.status,
                    "digest": evaluation.lint_result.digest,
                    "plan_digest": evaluation.lint_result.plan_digest,
                    "issues": to_primitive(evaluation.lint_result.issues),
                }
            ),
            mandatory=True,
        ),
        PlanningSourceDocument(
            "orchestration/compiled-graph.json",
            "Compiled task graph",
            "inspect dependencies and injected gates",
            TruthPartition.FUTURE_INTENT,
            _json_text(to_primitive(evaluation.graph)),
            mandatory=True,
        ),
        PlanningSourceDocument(
            "orchestration/simulation.json",
            "Plan simulation evidence",
            "inspect projected blockers, artifacts, and resource conflicts",
            TruthPartition.EVIDENCE,
            _json_text(to_primitive(evaluation.simulation)),
            mandatory=True,
        ),
    )


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
