"""Application-owned persistence contracts without SQLite knowledge."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class JobRepositoryPort(Protocol):
    path: Path

    def create(self, request: dict[str, Any], *, idempotency_key: str = "") -> dict[str, Any]: ...

    def read(self, job_id: str) -> dict[str, Any]: ...

    def update(self, job_id: str, **updates: object) -> dict[str, Any]: ...

    def claim(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> bool: ...

    def heartbeat(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> None: ...

    def recover_interrupted(self) -> list[str]: ...

    def health(self) -> dict[str, Any]: ...


@runtime_checkable
class WorkerPersistencePort(JobRepositoryPort, Protocol):
    """Atomic job, lock, resource-lease, and event surface for one worker."""

    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]: ...

    def events_since(self, job_id: str, after: int = 0, *, limit: int = 200) -> list[dict[str, Any]]: ...

    def acquire_lock(
        self,
        lock_key: str,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 120,
    ) -> bool: ...

    def release_lock(self, lock_key: str, job_id: str) -> None: ...

    def heartbeat_execution(
        self,
        job_id: str,
        worker_id: str,
        lock_key: str,
        *,
        lease_seconds: int = 60,
    ) -> None: ...

    def acquire_resource_lease(
        self,
        claim: dict[str, Any],
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
        conflicts: Callable[[dict[str, Any], dict[str, Any]], bool],
    ) -> str: ...

    def heartbeat_resource_execution(
        self,
        job_id: str,
        lease_owner: str,
        lease_id: str,
        *,
        lease_seconds: int,
    ) -> None: ...

    def release_resource_lease(self, lease_id: str, *, job_id: str) -> bool: ...


@runtime_checkable
class AutopilotRepositoryPort(Protocol):
    def create_autopilot_run(
        self,
        project_root: str,
        *,
        mode: str,
        runtime: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]: ...

    def read_autopilot_run(self, run_id: str) -> dict[str, Any]: ...

    def latest_autopilot_run(self, project_root: str) -> dict[str, Any] | None: ...

    def update_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]: ...

    def update_autopilot_run_policy(self, run_id: str, policy: dict[str, Any]) -> dict[str, Any]: ...

    def advance_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]: ...

    def acquire_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool: ...

    def renew_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool: ...

    def release_autopilot_lease(self, run_id: str, owner_id: str) -> None: ...

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]: ...

    def autopilot_events_since(
        self,
        run_id: str,
        after: int = 0,
        *,
        limit: int = 300,
    ) -> list[dict[str, Any]]: ...

    def latest_autopilot_event(self, run_id: str, event: str) -> dict[str, Any] | None: ...

    def record_delegated_decision(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def delegated_decisions(self, run_id: str) -> list[dict[str, Any]]: ...

    def recover_autopilot_runs(self) -> int: ...


@runtime_checkable
class SessionRepositoryPort(Protocol):
    def create_advisor_session(
        self,
        project_root: str,
        snapshot_digest: str,
        *,
        title: str = "项目问答",
    ) -> dict[str, Any]: ...

    def read_advisor_session(self, session_id: str) -> dict[str, Any]: ...

    def list_advisor_sessions(self, project_root: str, *, limit: int = 30) -> list[dict[str, Any]]: ...

    def list_agent_sessions(self, project_root: str, *, limit: int = 30) -> list[dict[str, Any]]: ...

    def append_advisor_message(self, session_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def save_advisor_memory(
        self,
        session_id: str,
        *,
        summary: str,
        preferences: list[str],
    ) -> dict[str, Any]: ...

    def save_delegation_policy(self, project_root: str, policy: dict[str, Any]) -> dict[str, Any]: ...

    def read_delegation_policy(self, project_root: str) -> dict[str, Any] | None: ...

    def upsert_agent_session(self, session_id: str, **fields: Any) -> dict[str, Any]: ...

    def read_agent_session(self, session_id: str) -> dict[str, Any]: ...


@runtime_checkable
class ContextLedgerRepositoryPort(Protocol):
    def record_context_ledger(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def read_context_ledger(self, ledger_id: str) -> dict[str, Any]: ...

    def list_context_ledgers(self, project_root: str, *, limit: int = 100) -> list[dict[str, Any]]: ...


@runtime_checkable
class MutationReceiptRepositoryPort(Protocol):
    def record_mutation_receipt(self, project_root: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def read_mutation_receipt(self, receipt_id: str) -> dict[str, Any]: ...

    def list_mutation_receipts(
        self,
        project_root: str,
        *,
        task_id: str = "",
        run_id: str = "",
        session_id: str = "",
        plan_id: str = "",
        change_group_id: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class LeaseRepositoryPort(Protocol):
    def acquire_resource_lease(
        self,
        claim: dict[str, Any],
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
        conflicts: Callable[[dict[str, Any], dict[str, Any]], bool],
    ) -> str: ...

    def renew_resource_lease(
        self,
        lease_id: str,
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
    ) -> bool: ...

    def release_resource_lease(self, lease_id: str, *, job_id: str) -> bool: ...

    def list_resource_leases(self, project_id: str = "") -> list[dict[str, Any]]: ...


@runtime_checkable
class PlanRepositoryPort(Protocol):
    def reserve_creative_plan_revision(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def finalize_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
        *,
        digest: str,
    ) -> dict[str, Any]: ...

    def read_creative_plan(self, plan_id: str) -> dict[str, Any]: ...

    def list_creative_plans(self, project_root: str, *, limit: int = 100) -> list[dict[str, Any]]: ...

    def read_creative_plan_revision(self, plan_id: str, revision: int) -> dict[str, Any]: ...

    def creative_plan_events(
        self,
        plan_id: str,
        *,
        after: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...

    def authorize_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
        *,
        authorized_by: str,
        reason: str,
        verified_revision_digest: str,
    ) -> dict[str, Any]: ...


@runtime_checkable
class AssetRevisionIndexPort(Protocol):
    def record_asset_transaction(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def list_asset_transactions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...

    def read_asset_revision(
        self,
        project_root: str,
        asset_id: str,
        revision: str,
    ) -> dict[str, Any]: ...

    def list_asset_revisions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class DurableEventStorePort(Protocol):
    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]: ...

    def events_since(self, job_id: str, after: int = 0, *, limit: int = 200) -> list[dict[str, Any]]: ...

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]: ...

    def autopilot_events_since(
        self,
        run_id: str,
        after: int = 0,
        *,
        limit: int = 300,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class UnitOfWorkPort(Protocol):
    def read(self) -> AbstractContextManager[Any]: ...

    def write(self, *, immediate: bool = False) -> AbstractContextManager[Any]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new_id(self, prefix: str) -> str: ...


@dataclass(frozen=True)
class PersistencePorts:
    """Named persistence capabilities for one application instance."""

    jobs: JobRepositoryPort
    autopilot: AutopilotRepositoryPort
    sessions: SessionRepositoryPort
    context_ledgers: ContextLedgerRepositoryPort
    mutation_receipts: MutationReceiptRepositoryPort
    leases: LeaseRepositoryPort
    plans: PlanRepositoryPort
    asset_revisions: AssetRevisionIndexPort
    events: DurableEventStorePort
    unit_of_work: UnitOfWorkPort
    facade: Any

    @property
    def worker(self) -> WorkerPersistencePort:
        """Return the atomic worker control aggregate during facade migration."""

        return self.facade


__all__ = [
    "AssetRevisionIndexPort",
    "AutopilotRepositoryPort",
    "Clock",
    "ContextLedgerRepositoryPort",
    "DurableEventStorePort",
    "IdGenerator",
    "JobRepositoryPort",
    "LeaseRepositoryPort",
    "MutationReceiptRepositoryPort",
    "PersistencePorts",
    "PlanRepositoryPort",
    "SessionRepositoryPort",
    "UnitOfWorkPort",
    "WorkerPersistencePort",
]
