"""Compose deterministic memory adapters into application persistence ports."""

from __future__ import annotations

from ...application.persistence_ports import PersistencePorts
from .assets import InMemoryAssetRevisionIndex
from .autopilot import InMemoryAutopilotRepository
from .facade import MemoryCompatibilityFacade
from .events import InMemoryDurableEventStore
from .jobs import InMemoryWorkerPersistence
from .plans import InMemoryPlanRepository
from .primitives import SystemClock, UuidIdGenerator
from .sessions import InMemorySessionRepository
from .state import MemoryPersistenceState
from .unit_of_work import MemoryUnitOfWork


def build_memory_persistence_ports(*, clock=None, ids=None) -> PersistencePorts:
    state = MemoryPersistenceState()
    selected_clock = clock or SystemClock()
    selected_ids = ids or UuidIdGenerator()
    jobs = InMemoryWorkerPersistence(state, selected_clock, selected_ids)
    autopilot = InMemoryAutopilotRepository(state, selected_clock, selected_ids)
    sessions = InMemorySessionRepository(state, selected_clock, selected_ids)
    plans = InMemoryPlanRepository(state, selected_clock)
    assets = InMemoryAssetRevisionIndex(state)
    events = InMemoryDurableEventStore(jobs, autopilot)
    facade = MemoryCompatibilityFacade(
        state,
        selected_clock,
        jobs=jobs,
        autopilot=autopilot,
        sessions=sessions,
        plans=plans,
        assets=assets,
    )
    return PersistencePorts(
        jobs=jobs,
        autopilot=autopilot,
        sessions=sessions,
        leases=jobs,
        plans=plans,
        asset_revisions=assets,
        events=events,
        unit_of_work=MemoryUnitOfWork(state),
        facade=facade,
    )


__all__ = ["build_memory_persistence_ports"]
