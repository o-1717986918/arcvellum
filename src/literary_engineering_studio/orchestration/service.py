"""AO-3 shadow service: plan with Agents, execute only the fixed route."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

from .agent_transport import OrchestrationAgentTransport
from .context_builder import AssembledPlanningContext, assemble_planning_context
from .defaults import DefaultPlanFactory
from .persistence import persist_shadow_revision
from .plan_events import CreativePlanEvent, CreativePlanEventType
from .planner import PlannerProtocolRun, run_planner
from .reviewer import (
    ReviewerProtocolRun,
    assemble_reviewer_context,
    run_reviewer,
)
from .settings import OrchestrationMode, OrchestrationSettings
from .shadow import ShadowPlanEvaluation, evaluate_completed_shadow_candidate
from .shadow_audit import (
    audit_reference,
    completed_comparison,
    fallback_event,
    record_fallback,
    write_events,
    write_json,
    write_shadow_evaluation,
)
from .shadow_run import ShadowOrchestrationResult, ShadowPlanningInput


@dataclass
class _ShadowRunState:
    request: ShadowPlanningInput
    root: Path
    operation_id: str
    plan_id: str
    audit_root: Path
    initial_fingerprint: str
    fixed_steps: int
    planner_context: AssembledPlanningContext | None = None
    planner_run: PlannerProtocolRun | None = None
    evaluation: ShadowPlanEvaluation | None = None
    review_context: AssembledPlanningContext | None = None
    reviewer_run: ReviewerProtocolRun | None = None
    events: list[CreativePlanEvent] = field(default_factory=list)


class ShadowOrchestrationService:
    """Coordinate Planner/Reviewer evidence without touching formal execution."""

    def __init__(
        self,
        settings: OrchestrationSettings,
        transport: OrchestrationAgentTransport,
    ):
        self.settings = settings
        self.transport = transport

    def run(self, request: ShadowPlanningInput) -> ShadowOrchestrationResult:
        if self.settings.effective_mode is not OrchestrationMode.SHADOW:
            state = self._initialize(request, require_fingerprint=False)
            reason = (
                "feature_off"
                if not self.settings.enabled
                else f"mode_not_available_in_ao3:{self.settings.effective_mode.value}"
            )
            return self._fallback(state, reason)
        try:
            state = self._initialize(request, require_fingerprint=True)
        except Exception as exc:
            return self._initialization_fallback(request, exc)
        for stage in (
            self._run_planner_stage,
            self._evaluate_stage,
            self._run_reviewer_stage,
        ):
            try:
                fallback = stage(state)
            except Exception as exc:
                return self._fallback(
                    state,
                    f"{stage.__name__.removeprefix('_run_').removesuffix('_stage')}_failed",
                    str(exc),
                )
            if fallback is not None:
                return fallback
        try:
            return self._finalize(state)
        except Exception as exc:
            return self._fallback(state, "shadow_finalize_failed", str(exc))

    def _initialize(
        self,
        request: ShadowPlanningInput,
        *,
        require_fingerprint: bool,
    ) -> _ShadowRunState:
        root = request.project_root.expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"work project not found: {root}")
        operation_id = "shadow-" + uuid4().hex[:16]
        audit_root = root / "workflow" / "orchestration" / "runs" / operation_id
        audit_root.mkdir(parents=True, exist_ok=False)
        fingerprint = (
            _required_fingerprint(request.fingerprint_provider())
            if require_fingerprint
            else "feature-disabled"
        )
        fixed = DefaultPlanFactory().create(
            base_project_fingerprint=fingerprint,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return _ShadowRunState(
            request=request,
            root=root,
            operation_id=operation_id,
            plan_id="plan-" + operation_id,
            audit_root=audit_root,
            initial_fingerprint=fingerprint,
            fixed_steps=len(fixed.route_sequence),
        )

    def _run_planner_stage(
        self,
        state: _ShadowRunState,
    ) -> ShadowOrchestrationResult | None:
        logical_session = f"{state.operation_id}:planner"
        state.planner_context = assemble_planning_context(
            state.request.sources,
            project_root_hash=_project_root_hash(state.root),
            session_id=logical_session,
            operation_id=state.operation_id,
            plan_id=state.plan_id,
        )
        write_json(
            state.audit_root / "planner" / "context-ledger.json",
            state.planner_context.ledger.as_dict(),
        )
        try:
            state.planner_run = run_planner(
                self.transport,
                plan_id=state.plan_id,
                revision=state.request.normalization_context.revision,
                logical_session_id=logical_session,
                objective=state.request.objective,
                context=state.planner_context,
                subject_digests=tuple(
                    item.sha256
                    for item in state.planner_context.ledger.entries
                    if item.included
                ),
                audit_root=state.audit_root / "planner",
            )
        except Exception as exc:
            return self._fallback(state, "planner_failed", str(exc))
        state.events.append(state.planner_run.completed_event)
        write_events(state.audit_root / "events.jsonl", state.events)
        if self._is_stale(state):
            return self._fallback(state, "stale_context_after_planner")
        return None

    def _evaluate_stage(
        self,
        state: _ShadowRunState,
    ) -> ShadowOrchestrationResult | None:
        assert state.planner_run is not None
        try:
            state.evaluation = evaluate_completed_shadow_candidate(
                state.planner_run.completed_event,
                normalization_context=replace(
                    state.request.normalization_context,
                    base_project_fingerprint=state.initial_fingerprint,
                    plan_id=state.plan_id,
                ),
                lint_context=replace(
                    state.request.lint_context,
                    current_project_fingerprint=state.initial_fingerprint,
                ),
                simulation_context_factory=state.request.simulation_context_factory,
            )
        except Exception as exc:
            return self._fallback(state, "planner_candidate_invalid", str(exc))
        if state.evaluation.passed:
            return None
        self._write_evaluation(state)
        reason = (
            "plan_lint_failed"
            if not state.evaluation.lint_result.passed
            else "plan_simulation_failed"
        )
        return self._fallback(state, reason)

    def _run_reviewer_stage(
        self,
        state: _ShadowRunState,
    ) -> ShadowOrchestrationResult | None:
        assert state.planner_context is not None
        assert state.planner_run is not None
        assert state.evaluation is not None
        assert state.evaluation.graph is not None
        assert state.evaluation.simulation is not None
        logical_session = f"{state.operation_id}:reviewer"
        try:
            state.review_context = assemble_reviewer_context(
                project_root_hash=_project_root_hash(state.root),
                operation_id=state.operation_id,
                logical_session_id=logical_session,
                plan_id=state.plan_id,
                planner_context=state.planner_context,
                planner_run=state.planner_run,
                evaluation=state.evaluation,
            )
            write_json(
                state.audit_root / "reviewer" / "context-ledger.json",
                state.review_context.ledger.as_dict(),
            )
            state.reviewer_run = run_reviewer(
                self.transport,
                planner_session_id=state.planner_run.response.session_id,
                logical_session_id=logical_session,
                context=state.review_context,
                plan=state.evaluation.plan,
                graph=state.evaluation.graph,
                lint_result=state.evaluation.lint_result,
                simulation=state.evaluation.simulation,
                audit_root=state.audit_root / "reviewer",
            )
        except Exception as exc:
            self._write_evaluation(state)
            return self._fallback(state, "review_failed", str(exc))
        state.events.append(
            CreativePlanEvent(
                event_type=CreativePlanEventType.REVIEW_COMPLETED,
                plan_id=state.plan_id,
                revision=state.evaluation.plan.revision,
                session_id=state.reviewer_run.response.session_id,
                sequence=len(state.events),
                data={"review": state.reviewer_run.receipt.as_dict()},
            )
        )
        write_events(state.audit_root / "events.jsonl", state.events)
        if self._is_stale(state):
            self._write_evaluation(state)
            return self._fallback(state, "stale_context_after_review")
        return None

    def _finalize(self, state: _ShadowRunState) -> ShadowOrchestrationResult:
        assert state.planner_run is not None
        assert state.evaluation is not None
        assert state.evaluation.graph is not None
        assert state.evaluation.simulation is not None
        assert state.reviewer_run is not None
        if self._is_stale(state):
            return self._fallback(state, "stale_context_before_persistence")
        comparison = completed_comparison(
            fixed_steps=state.fixed_steps,
            planner_run=state.planner_run,
            evaluation=state.evaluation,
            reviewer_run=state.reviewer_run,
        )
        self._write_evaluation(state, comparison=comparison)
        if self._is_stale(state):
            return self._fallback(state, "stale_context_before_persistence")
        artifacts = self._persist_revision(state)
        accepted = state.reviewer_run.receipt.activation_eligible
        fallback_reason = "" if accepted else "orchestration_review_rejected"
        if fallback_reason:
            state.events.append(
                fallback_event(
                    state.plan_id,
                    state.evaluation.plan.revision,
                    state.reviewer_run.response.session_id,
                    len(state.events),
                    fallback_reason,
                )
            )
            write_events(state.audit_root / "events.jsonl", state.events)
        return ShadowOrchestrationResult(
            operation_id=state.operation_id,
            plan_id=state.plan_id,
            status="shadow_completed" if accepted else "fixed_fallback",
            execution_route="fixed",
            fallback_reason=fallback_reason,
            audit_root=audit_reference(state.audit_root),
            planner_session_id=state.planner_run.response.session_id,
            reviewer_session_id=state.reviewer_run.response.session_id,
            evaluation=state.evaluation,
            reviewer_run=state.reviewer_run,
            artifacts=artifacts,
            comparison=comparison,
            events=tuple(state.events),
        )

    def _persist_revision(self, state: _ShadowRunState):
        if state.request.store is None:
            return None
        assert state.planner_run is not None
        assert state.evaluation is not None
        assert state.evaluation.graph is not None
        assert state.evaluation.simulation is not None
        assert state.reviewer_run is not None
        assert state.review_context is not None
        return persist_shadow_revision(
            state.root,
            store=state.request.store,
            candidate_payload=state.planner_run.completed_event.data["candidate"],
            plan=state.evaluation.plan,
            graph=state.evaluation.graph,
            lint_result=state.evaluation.lint_result,
            simulation=state.evaluation.simulation,
            review_receipt=state.reviewer_run.receipt,
            review_context_digest=state.review_context.ledger.digest,
        )

    def _write_evaluation(self, state: _ShadowRunState, *, comparison=None) -> None:
        assert state.planner_run is not None
        assert state.planner_context is not None
        assert state.evaluation is not None
        write_shadow_evaluation(
            state.audit_root,
            state.planner_run,
            state.planner_context,
            state.evaluation,
            reviewer_run=state.reviewer_run,
            review_context=state.review_context,
            comparison=comparison,
        )

    def _fallback(
        self,
        state: _ShadowRunState,
        reason: str,
        detail: str = "",
    ) -> ShadowOrchestrationResult:
        arguments = self._fallback_arguments(state, reason, detail)
        try:
            return record_fallback(
                state.operation_id,
                state.plan_id,
                state.audit_root,
                **arguments,
            )
        except Exception:
            return self._memory_fallback(state, reason)

    def _initialization_fallback(
        self,
        request: ShadowPlanningInput,
        exc: Exception,
    ) -> ShadowOrchestrationResult:
        try:
            state = self._initialize(request, require_fingerprint=False)
        except Exception:
            root = request.project_root.expanduser().resolve()
            operation_id = "shadow-" + uuid4().hex[:16]
            state = _ShadowRunState(
                request=request,
                root=root,
                operation_id=operation_id,
                plan_id="plan-" + operation_id,
                audit_root=root / "workflow" / "orchestration" / "runs" / operation_id,
                initial_fingerprint="",
                fixed_steps=0,
            )
        return self._fallback(state, "shadow_initialization_failed", str(exc))

    @staticmethod
    def _fallback_arguments(
        state: _ShadowRunState,
        reason: str,
        detail: str,
    ) -> dict[str, object]:
        return {
            "reason": reason,
            "detail": detail,
            "fixed_steps": state.fixed_steps,
            "planner_session_id": (
                state.planner_run.response.session_id if state.planner_run else ""
            ),
            "reviewer_session_id": (
                state.reviewer_run.response.session_id if state.reviewer_run else ""
            ),
            "evaluation": state.evaluation,
            "reviewer_run": state.reviewer_run,
            "events": state.events,
        }

    @staticmethod
    def _memory_fallback(
        state: _ShadowRunState,
        reason: str,
    ) -> ShadowOrchestrationResult:
        return ShadowOrchestrationResult(
            operation_id=state.operation_id,
            plan_id=state.plan_id,
            status="fixed_fallback",
            execution_route="fixed",
            fallback_reason=reason,
            audit_root=audit_reference(state.audit_root),
        )

    @staticmethod
    def _is_stale(state: _ShadowRunState) -> bool:
        return state.request.fingerprint_provider() != state.initial_fingerprint


def _project_root_hash(root: Path) -> str:
    return hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()


def _required_fingerprint(value: str) -> str:
    fingerprint = str(value or "").strip()
    if not fingerprint:
        raise ValueError("project fingerprint is required")
    return fingerprint
