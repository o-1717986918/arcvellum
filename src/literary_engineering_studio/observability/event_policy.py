"""Shared durability policy for high-frequency Agent Runtime events."""

from __future__ import annotations


EPHEMERAL_RUNTIME_EVENTS = frozenset(
    {
        "agent.message.delta",
        "runner.reasoning.activity",
        "runner.session.status",
    }
)


def canonical_runtime_event(event: str) -> str:
    """Remove the durable Autopilot namespace without changing event meaning."""

    normalized = str(event or "").strip()
    return normalized[7:] if normalized.startswith("worker.") else normalized


def is_ephemeral_runtime_event(event: str) -> bool:
    return canonical_runtime_event(event) in EPHEMERAL_RUNTIME_EVENTS


def should_persist_runtime_event(event: str) -> bool:
    return not is_ephemeral_runtime_event(event)


__all__ = [
    "EPHEMERAL_RUNTIME_EVENTS",
    "canonical_runtime_event",
    "is_ephemeral_runtime_event",
    "should_persist_runtime_event",
]
