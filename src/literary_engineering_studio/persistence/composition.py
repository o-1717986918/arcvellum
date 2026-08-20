"""Compose existing SQLite repositories into application-owned ports."""

from __future__ import annotations

from ..application.persistence_ports import PersistencePorts
from .job_store import JobStore


def sqlite_persistence_ports(store: JobStore) -> PersistencePorts:
    """Expose one SQLite aggregate through named capabilities without wrappers."""

    return PersistencePorts(
        jobs=store,
        autopilot=store.autopilot_runs,
        sessions=store.sessions,
        leases=store.resource_leases,
        plans=store.creative_plans,
        asset_revisions=store.asset_history,
        events=store,
        unit_of_work=store.unit_of_work,
        facade=store,
    )


__all__ = ["sqlite_persistence_ports"]
