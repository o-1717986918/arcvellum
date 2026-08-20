"""Explicit aggregate bridge for callers not yet migrated to named ports."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...persistence.facade import RepositoryMethod
from .primitives import iso_now


class MemoryCompatibilityFacade:
    create = RepositoryMethod("jobs")
    read = RepositoryMethod("jobs")
    update = RepositoryMethod("jobs")
    claim = RepositoryMethod("jobs")
    heartbeat = RepositoryMethod("jobs")
    recover_interrupted = RepositoryMethod("jobs")
    append_event = RepositoryMethod("jobs")
    events_since = RepositoryMethod("jobs")
    acquire_lock = RepositoryMethod("jobs")
    release_lock = RepositoryMethod("jobs")
    heartbeat_execution = RepositoryMethod("jobs")
    acquire_resource_lease = RepositoryMethod("jobs")
    renew_resource_lease = RepositoryMethod("jobs")
    heartbeat_resource_execution = RepositoryMethod("jobs")
    release_resource_lease = RepositoryMethod("jobs")
    list_resource_leases = RepositoryMethod("jobs")
    health = RepositoryMethod("jobs")

    create_autopilot_run = RepositoryMethod("autopilot_runs")
    read_autopilot_run = RepositoryMethod("autopilot_runs")
    latest_autopilot_run = RepositoryMethod("autopilot_runs")
    update_autopilot_run = RepositoryMethod("autopilot_runs")
    update_autopilot_run_policy = RepositoryMethod("autopilot_runs")
    advance_autopilot_run = RepositoryMethod("autopilot_runs")
    acquire_autopilot_lease = RepositoryMethod("autopilot_runs")
    renew_autopilot_lease = RepositoryMethod("autopilot_runs")
    release_autopilot_lease = RepositoryMethod("autopilot_runs")
    append_autopilot_event = RepositoryMethod("autopilot_runs")
    autopilot_events_since = RepositoryMethod("autopilot_runs")
    latest_autopilot_event = RepositoryMethod("autopilot_runs")
    record_delegated_decision = RepositoryMethod("autopilot_runs")
    delegated_decisions = RepositoryMethod("autopilot_runs")
    recover_autopilot_runs = RepositoryMethod("autopilot_runs")

    create_advisor_session = RepositoryMethod("sessions")
    read_advisor_session = RepositoryMethod("sessions")
    list_advisor_sessions = RepositoryMethod("sessions")
    append_advisor_message = RepositoryMethod("sessions")
    save_advisor_memory = RepositoryMethod("sessions")
    save_delegation_policy = RepositoryMethod("sessions")
    read_delegation_policy = RepositoryMethod("sessions")
    upsert_agent_session = RepositoryMethod("sessions")
    read_agent_session = RepositoryMethod("sessions")
    list_agent_sessions = RepositoryMethod("sessions")

    reserve_creative_plan_revision = RepositoryMethod("creative_plans")
    finalize_creative_plan_revision = RepositoryMethod("creative_plans")
    read_creative_plan = RepositoryMethod("creative_plans")
    list_creative_plans = RepositoryMethod("creative_plans")
    read_creative_plan_revision = RepositoryMethod("creative_plans")
    authorize_creative_plan_revision = RepositoryMethod("creative_plans")
    creative_plan_events = RepositoryMethod("creative_plans")

    record_asset_transaction = RepositoryMethod("asset_history")
    list_asset_transactions = RepositoryMethod("asset_history")
    read_asset_revision = RepositoryMethod("asset_history")
    list_asset_revisions = RepositoryMethod("asset_history")

    def __init__(self, state, clock, *, jobs, autopilot, sessions, plans, assets):
        self._state = state
        self._clock = clock
        self.jobs = jobs
        self.autopilot_runs = autopilot
        self.sessions = sessions
        self.creative_plans = plans
        self.asset_history = assets
        self.path = jobs.path

    def record_context_ledger(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            record = {
                **deepcopy(payload),
                "project_root": project_root,
                "recorded_at": iso_now(self._clock),
            }
            self._state.context_ledgers.setdefault(project_root, []).append(record)
            return deepcopy(record)

    def record_mutation_receipt(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            record = {
                **deepcopy(payload),
                "project_root": project_root,
                "recorded_at": iso_now(self._clock),
            }
            self._state.mutation_receipts.setdefault(project_root, []).append(record)
            return deepcopy(record)


__all__ = ["MemoryCompatibilityFacade"]
