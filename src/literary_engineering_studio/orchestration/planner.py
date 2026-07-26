"""Planner protocol runner that emits typed, non-executable plan events."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .agent_protocol import OrchestrationAgentRequest
from .agent_transport import (
    OrchestrationAgentResponse,
    OrchestrationAgentTransport,
)
from .context_builder import AssembledPlanningContext
from .plan_events import CreativePlanEvent, CreativePlanEventType
from .profiles import OrchestrationAgentRole


@dataclass(frozen=True)
class PlannerProtocolRun:
    response: OrchestrationAgentResponse
    request: OrchestrationAgentRequest
    events: tuple[CreativePlanEvent, ...]

    @property
    def completed_event(self) -> CreativePlanEvent:
        return self.events[-1]


def run_planner(
    transport: OrchestrationAgentTransport,
    *,
    plan_id: str,
    revision: int,
    logical_session_id: str,
    objective: str,
    context: AssembledPlanningContext,
    subject_digests: tuple[str, ...],
    audit_root: Path,
) -> PlannerProtocolRun:
    request = OrchestrationAgentRequest(
        request_id=f"{plan_id}:planner:{revision}",
        session_id=logical_session_id,
        role=OrchestrationAgentRole.PLANNER,
        objective=objective,
        context_ledger_id=context.ledger.ledger_id,
        context_ledger_digest=context.ledger.digest,
        subject_digests=subject_digests,
    )
    response = transport.invoke(
        OrchestrationAgentRole.PLANNER,
        prompt=_planner_prompt(request, context),
        audit_root=audit_root,
    )
    if not response.session_id:
        raise RuntimeError("Planner runtime did not return an actual session identity")
    sequence = 0
    events: list[CreativePlanEvent] = []
    for delta in response.deltas:
        if not delta:
            continue
        events.append(
            CreativePlanEvent(
                event_type=CreativePlanEventType.CANDIDATE_DELTA,
                plan_id=plan_id,
                revision=revision,
                session_id=response.session_id,
                sequence=sequence,
                data={"text": delta},
            )
        )
        sequence += 1
    events.append(
        CreativePlanEvent(
            event_type=CreativePlanEventType.CANDIDATE_COMPLETED,
            plan_id=plan_id,
            revision=revision,
            session_id=response.session_id,
            sequence=sequence,
            data={"candidate": response.payload},
        )
    )
    return PlannerProtocolRun(response=response, request=request, events=tuple(events))


def _planner_prompt(
    request: OrchestrationAgentRequest,
    context: AssembledPlanningContext,
) -> str:
    return "\n\n".join(
        (
            "# ArcVellum Orchestration Planner",
            "Return exactly one JSON object and no commentary or Markdown fence.",
            "The JSON must match output_schema in the machine request.",
            "You may propose literary strategy and task dependencies. You may not declare commands, paths, "
            "machine-owned fields, completed facts, formal writes, or remove mandatory gates.",
            "## Machine request\n" + json.dumps(request.as_dict(), ensure_ascii=False, indent=2),
            "## Bounded planning context\n" + context.text,
        )
    )
