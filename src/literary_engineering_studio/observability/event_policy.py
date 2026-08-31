"""Shared durability policy for high-frequency Agent Runtime events."""

from __future__ import annotations

from enum import Enum


class EventDurability(str, Enum):
    DURABLE = "durable"
    EPHEMERAL = "ephemeral"


EPHEMERAL_RUNTIME_EVENTS = frozenset(
    {
        "agent.message.delta",
        "artifact.preview.delta",
        "artifact.preview.snapshot",
        "runner.reasoning.activity",
        "runner.session.status",
    }
)


def canonical_runtime_event(event: str) -> str:
    """Remove the durable Autopilot namespace without changing event meaning."""

    normalized = str(event or "").strip()
    return normalized[7:] if normalized.startswith("worker.") else normalized


def is_ephemeral_runtime_event(event: str) -> bool:
    return classify_runtime_event(event) is EventDurability.EPHEMERAL


def classify_runtime_event(event: str) -> EventDurability:
    canonical = canonical_runtime_event(event)
    return (
        EventDurability.EPHEMERAL
        if canonical in EPHEMERAL_RUNTIME_EVENTS
        else EventDurability.DURABLE
    )


def should_persist_runtime_event(event: str) -> bool:
    return classify_runtime_event(event) is EventDurability.DURABLE


__all__ = [
    "EPHEMERAL_RUNTIME_EVENTS",
    "EventDurability",
    "canonical_runtime_event",
    "classify_runtime_event",
    "is_ephemeral_runtime_event",
    "should_persist_runtime_event",
]
