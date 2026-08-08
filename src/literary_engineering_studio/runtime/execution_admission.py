"""One admission entry combining process and durable resource ownership."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .execution_coordinator import ProjectExecutionCoordinator
from .resources import (
    ResourceClaim,
    claims_conflict,
    project_identity,
    resource_claim_from_dict,
)


@dataclass(frozen=True)
class ExecutionAdmission:
    project_root: str
    coordinator_owner: str
    job_id: str
    lock_key: str = ""
    resource_lease_id: str = ""

    @property
    def resource_mode(self) -> bool:
        return bool(self.resource_lease_id)


def acquire_execution_admission(
    store: Any,
    coordinator: ProjectExecutionCoordinator,
    *,
    project_root: str,
    job_id: str,
    worker_id: str,
    lock_key: str,
    lease_seconds: int,
    resource_claim: ResourceClaim | None,
) -> ExecutionAdmission | None:
    if resource_claim is None:
        return _acquire_exclusive(
            store,
            coordinator,
            project_root=project_root,
            job_id=job_id,
            worker_id=worker_id,
            lock_key=lock_key,
            lease_seconds=lease_seconds,
        )
    _validate_read_only_claim(project_root, resource_claim)
    if not coordinator.acquire_claim(project_root, job_id, resource_claim):
        return None
    lease_id = store.acquire_resource_lease(
        resource_claim.as_dict(),
        job_id=job_id,
        lease_owner=worker_id,
        lease_seconds=lease_seconds * 2,
        conflicts=_payloads_conflict,
    )
    if not lease_id:
        coordinator.release(project_root, job_id)
        return None
    store.append_event(
        job_id,
        "resource.lock.acquired",
        {"lease_id": lease_id, "claim": resource_claim.as_dict()},
    )
    return ExecutionAdmission(
        project_root=project_root,
        coordinator_owner=job_id,
        job_id=job_id,
        resource_lease_id=lease_id,
    )


def release_execution_admission(
    store: Any,
    coordinator: ProjectExecutionCoordinator,
    admission: ExecutionAdmission,
) -> None:
    try:
        if admission.resource_mode:
            released = store.release_resource_lease(
                admission.resource_lease_id,
                job_id=admission.job_id,
            )
            store.append_event(
                admission.job_id,
                "resource.lock.released",
                {
                    "lease_id": admission.resource_lease_id,
                    "released": released,
                },
            )
        else:
            store.release_lock(admission.lock_key, admission.job_id)
    finally:
        coordinator.release(admission.project_root, admission.coordinator_owner)


def heartbeat_execution_admission(
    store: Any,
    admission: ExecutionAdmission,
    *,
    worker_id: str,
    lease_seconds: int,
) -> None:
    if admission.resource_mode:
        store.heartbeat_resource_execution(
            admission.job_id,
            worker_id,
            admission.resource_lease_id,
            lease_seconds=lease_seconds,
        )
        return
    store.heartbeat_execution(
        admission.job_id,
        worker_id,
        admission.lock_key,
        lease_seconds=lease_seconds,
    )


def _acquire_exclusive(
    store: Any,
    coordinator: ProjectExecutionCoordinator,
    *,
    project_root: str,
    job_id: str,
    worker_id: str,
    lock_key: str,
    lease_seconds: int,
) -> ExecutionAdmission | None:
    if not coordinator.acquire(project_root, job_id):
        return None
    if not store.acquire_lock(
        lock_key,
        job_id,
        worker_id,
        lease_seconds=lease_seconds * 2,
    ):
        coordinator.release(project_root, job_id)
        return None
    return ExecutionAdmission(
        project_root=project_root,
        coordinator_owner=job_id,
        job_id=job_id,
        lock_key=lock_key,
    )


def _validate_read_only_claim(project_root: str, claim: ResourceClaim) -> None:
    if claim.project_id != project_identity(Path(project_root)):
        raise ValueError("resource claim project does not match supervised project")
    if claim.writes or claim.exclusive_barriers:
        raise ValueError(
            "first-phase resource admission accepts read-only claims only"
        )


def _payloads_conflict(left: dict[str, object], right: dict[str, object]) -> bool:
    return claims_conflict(
        resource_claim_from_dict(left),
        resource_claim_from_dict(right),
    ).conflicts
