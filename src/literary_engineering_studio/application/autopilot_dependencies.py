"""Resolve Autopilot persistence ports across the migration window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..observability.agent_session_tracking import AgentSessionEventProjector
from .persistence_ports import AutopilotRepositoryPort, PlanRepositoryPort, SessionRepositoryPort


@dataclass(frozen=True)
class AutopilotPersistenceDependencies:
    runs: AutopilotRepositoryPort
    sessions: SessionRepositoryPort
    plans: PlanRepositoryPort
    session_event_tracker: Callable[..., object]


def resolve_autopilot_persistence(
    legacy_store: Any | None,
    *,
    runs: AutopilotRepositoryPort | None,
    sessions: SessionRepositoryPort | None,
    plans: PlanRepositoryPort | None,
    session_event_tracker: Callable[..., object] | None,
) -> AutopilotPersistenceDependencies:
    selected_runs = runs or legacy_store
    selected_sessions = sessions or legacy_store
    selected_plans = plans or legacy_store
    if selected_runs is None or selected_sessions is None or selected_plans is None:
        raise TypeError("AutopilotService requires runs, sessions, and plans ports")
    if session_event_tracker is None:
        if legacy_store is None:
            raise TypeError("named Autopilot ports require a session event tracker")
        session_event_tracker = AgentSessionEventProjector(legacy_store, legacy_store, legacy_store)
    return AutopilotPersistenceDependencies(
        runs=selected_runs,
        sessions=selected_sessions,
        plans=selected_plans,
        session_event_tracker=session_event_tracker,
    )


__all__ = ["AutopilotPersistenceDependencies", "resolve_autopilot_persistence"]
