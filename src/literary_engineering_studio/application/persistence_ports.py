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
    leases: LeaseRepositoryPort
    plans: PlanRepositoryPort
    asset_revisions: AssetRevisionIndexPort
    events: DurableEventStorePort
    unit_of_work: UnitOfWorkPort
    facade: Any


__all__ = [
    "AssetRevisionIndexPort",
    "AutopilotRepositoryPort",
    "Clock",
    "DurableEventStorePort",
    "IdGenerator",
    "JobRepositoryPort",
    "LeaseRepositoryPort",
    "PersistencePorts",
    "PlanRepositoryPort",
    "SessionRepositoryPort",
    "UnitOfWorkPort",
]
