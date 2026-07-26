"""Typed creative-plan events and display-only streaming deltas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


CREATIVE_PLAN_EVENT_SCHEMA = "arcvellum/creative-plan-event/v1"


class CreativePlanEventType(str, Enum):
    CANDIDATE_DELTA = "plan.candidate.delta"
    CANDIDATE_COMPLETED = "plan.candidate.completed"
    REVISION_RESERVED = "plan.revision.reserved"
    REVISION_READY = "plan.revision.ready"
    REVIEW_COMPLETED = "plan.review.completed"
    ACTIVATED = "plan.activated"
    REJECTED = "plan.rejected"
    STALE = "plan.stale"
    FALLBACK = "plan.fallback"

    @property
    def display_only(self) -> bool:
        return self is CreativePlanEventType.CANDIDATE_DELTA


@dataclass(frozen=True)
class CreativePlanEvent:
    event_type: CreativePlanEventType
    plan_id: str
    revision: int
    session_id: str
    sequence: int
    data: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("creative plan event plan_id is required")
        if self.revision < 1 or self.sequence < 0:
            raise ValueError("creative plan event revision and sequence are invalid")
        if not self.session_id.strip():
            raise ValueError("creative plan event session_id is required")
        _validate_event_data(self.event_type, self.data)

    @property
    def display_only(self) -> bool:
        return self.event_type.display_only

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": CREATIVE_PLAN_EVENT_SCHEMA,
            "event": self.event_type.value,
            "plan_id": self.plan_id,
            "revision": self.revision,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "display_only": self.display_only,
            "data": self.data,
        }


def parse_creative_plan_event(payload: Mapping[str, Any]) -> CreativePlanEvent:
    if str(payload.get("schema") or "") != CREATIVE_PLAN_EVENT_SCHEMA:
        raise ValueError("unsupported creative plan event schema")
    raw_data = payload.get("data")
    if not isinstance(raw_data, dict):
        raise ValueError("creative plan event data must be an object")
    event = CreativePlanEvent(
        event_type=CreativePlanEventType(str(payload.get("event") or "")),
        plan_id=str(payload.get("plan_id") or ""),
        revision=int(payload.get("revision") or 0),
        session_id=str(payload.get("session_id") or ""),
        sequence=int(payload.get("sequence") or 0),
        data=dict(raw_data),
    )
    if bool(payload.get("display_only")) != event.display_only:
        raise ValueError("creative plan event display_only is machine-owned")
    return event


def completed_candidate_from_event(event: CreativePlanEvent) -> dict[str, Any]:
    if event.event_type is not CreativePlanEventType.CANDIDATE_COMPLETED:
        raise ValueError("Plan Lint only accepts a completed candidate event")
    candidate = event.data.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("completed creative plan event lacks a candidate object")
    return dict(candidate)


def _validate_event_data(event_type: CreativePlanEventType, data: dict[str, Any]) -> None:
    if event_type is CreativePlanEventType.CANDIDATE_DELTA:
        if set(data) != {"text"} or not isinstance(data.get("text"), str):
            raise ValueError("candidate delta data must contain only text")
        return
    if event_type is CreativePlanEventType.CANDIDATE_COMPLETED:
        if set(data) != {"candidate"} or not isinstance(data.get("candidate"), dict):
            raise ValueError("candidate completion data must contain only candidate")
