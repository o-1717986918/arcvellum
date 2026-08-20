"""In-memory worker aggregate with job, lock, lease, and event semantics."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import hashlib
from pathlib import Path
from typing import Any, Callable

from ...persistence.primitives import EVENT_SCHEMA, JOB_SCHEMA, _public_request, _redact
from .primitives import iso_now
from .state import MemoryPersistenceState


class InMemoryWorkerPersistence:
    path = Path(":memory:")

    def __init__(self, state: MemoryPersistenceState, clock, ids):
        self._state = state
        self._clock = clock
        self._ids = ids

    def create(self, request: dict[str, Any], *, idempotency_key: str = "") -> dict[str, Any]:
        normalized = str(idempotency_key or "").strip()
        with self._state.lock:
            if normalized:
                existing = next(
                    (item for item in self._state.jobs.values() if item["idempotency_key"] == normalized),
                    None,
                )
                if existing is not None:
                    return deepcopy(existing)
            job_id = self._ids.new_id("job")
            now = iso_now(self._clock)
            record = {
                "schema": JOB_SCHEMA,
                "job_id": job_id,
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "started_at": "",
                "finished_at": "",
                "request": deepcopy(request),
                "result": {},
                "error": "",
                "lease_owner": "",
                "lease_expires_at": "",
                "heartbeat_at": "",
                "idempotency_key": normalized,
                "revision": 0,
            }
            self._state.jobs[job_id] = record
            self._append_event(job_id, "run.queued", {"request": _public_request(request)})
            return deepcopy(record)

    def read(self, job_id: str) -> dict[str, Any]:
        with self._state.lock:
            return deepcopy(self._required_job(job_id))

    def update(self, job_id: str, **updates: object) -> dict[str, Any]:
        allowed = {
            "status", "started_at", "finished_at", "result", "error",
            "lease_owner", "lease_expires_at", "heartbeat_at",
        }
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ValueError("unsupported job fields: " + ", ".join(unknown))
        with self._state.lock:
            record = self._required_job(job_id)
            previous_status = record["status"]
            record.update(deepcopy(updates))
            record["updated_at"] = iso_now(self._clock)
            record["revision"] += 1
            if updates.get("status") and updates["status"] != previous_status:
                self._append_event(job_id, f"run.{updates['status']}", {"status": updates["status"]})
            return deepcopy(record)

    def claim(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> bool:
        with self._state.lock:
            record = self._required_job(job_id)
            if record["status"] not in {"queued", "interrupted"}:
                return False
            now = self._clock.now()
            stamp = iso_now(self._clock)
            record.update(
                status="running",
                started_at=record["started_at"] or stamp,
                updated_at=stamp,
                lease_owner=worker_id,
                lease_expires_at=(now + timedelta(seconds=max(10, lease_seconds))).isoformat(),
                heartbeat_at=stamp,
                revision=record["revision"] + 1,
            )
            self._append_event(job_id, "run.started", {"worker_id": worker_id})
            return True

    def heartbeat(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> None:
        with self._state.lock:
            record = self._owned_active_job(job_id, worker_id)
            stamp = iso_now(self._clock)
            record.update(
                heartbeat_at=stamp,
                updated_at=stamp,
                lease_expires_at=(self._clock.now() + timedelta(seconds=max(10, lease_seconds))).isoformat(),
            )

    def heartbeat_execution(
        self,
        job_id: str,
        worker_id: str,
        lock_key: str,
        *,
        lease_seconds: int = 60,
    ) -> None:
        with self._state.lock:
            self.heartbeat(job_id, worker_id, lease_seconds=lease_seconds)
            lock = self._state.project_locks.get(lock_key)
            if not lock or lock["job_id"] != job_id or lock["lease_owner"] != worker_id:
                raise RuntimeError(f"project execution lease is not owned by {worker_id}: {lock_key}")
            lock["updated_at"] = iso_now(self._clock)
            lock["lease_expires_at"] = (
                self._clock.now() + timedelta(seconds=max(30, lease_seconds * 2))
            ).isoformat()

    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            self._required_job(job_id)
            return deepcopy(self._append_event(job_id, event_type, data))

    def events_since(self, job_id: str, after: int = 0, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._state.lock:
            self._required_job(job_id)
            events = self._state.job_events.get(job_id, [])
            return deepcopy([item for item in events if item["sequence"] > max(0, int(after))][:max(1, int(limit))])

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        with self._state.lock:
            for job_id, record in self._state.jobs.items():
                if record["status"] not in {"running", "stopping"}:
                    continue
                record.update(
                    status="interrupted",
                    updated_at=iso_now(self._clock),
                    lease_owner="",
                    lease_expires_at="",
                    heartbeat_at="",
                    revision=record["revision"] + 1,
                )
                self._append_event(job_id, "run.interrupted", {"reason": "application-restart"})
                recovered.append(job_id)
        return recovered

    def acquire_lock(
        self,
        lock_key: str,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 120,
    ) -> bool:
        if not lock_key.strip():
            raise ValueError("lock key must not be empty")
        with self._state.lock:
            self._required_job(job_id)
            self._discard_expired_locks()
            current = self._state.project_locks.get(lock_key)
            if current and current["job_id"] != job_id:
                return False
            stamp = iso_now(self._clock)
            self._state.project_locks[lock_key] = {
                "job_id": job_id,
                "lease_owner": worker_id,
                "lease_expires_at": (
                    self._clock.now() + timedelta(seconds=max(30, lease_seconds))
                ).isoformat(),
                "updated_at": stamp,
            }
            self._append_event(job_id, "lock.acquired", {"lock_key": lock_key})
            return True

    def release_lock(self, lock_key: str, job_id: str) -> None:
        with self._state.lock:
            current = self._state.project_locks.get(lock_key)
            if current and current["job_id"] == job_id:
                del self._state.project_locks[lock_key]
            self._append_event(job_id, "lock.released", {"lock_key": lock_key})

    def acquire_resource_lease(
        self,
        claim: dict[str, Any],
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
        conflicts: Callable[[dict[str, Any], dict[str, Any]], bool],
    ) -> str:
        project_id = str(claim.get("project_id") or "").strip()
        task_node_id = str(claim.get("task_node_id") or "").strip()
        if not project_id or not task_node_id:
            raise ValueError("resource claim project_id and task_node_id are required")
        lease_id = "resource-" + hashlib.sha256(f"{job_id}|{task_node_id}".encode()).hexdigest()[:24]
        with self._state.lock:
            self._discard_expired_resource_leases()
            for current_id, current in self._state.resource_leases.items():
                if current_id == lease_id:
                    if current["claim"] != claim:
                        raise RuntimeError("resource lease identity was reused with another claim")
                    continue
                if current["project_id"] == project_id and conflicts(claim, current["claim"]):
                    return ""
            stamp = iso_now(self._clock)
            self._state.resource_leases[lease_id] = {
                "lease_id": lease_id,
                "project_id": project_id,
                "task_node_id": task_node_id,
                "job_id": job_id,
                "lease_owner": lease_owner,
                "claim": deepcopy(claim),
                "lease_expires_at": (
                    self._clock.now() + timedelta(seconds=max(30, lease_seconds))
                ).isoformat(),
                "updated_at": stamp,
            }
            return lease_id

    def heartbeat_resource_execution(
        self,
        job_id: str,
        lease_owner: str,
        lease_id: str,
        *,
        lease_seconds: int,
    ) -> None:
        with self._state.lock:
            self.heartbeat(job_id, lease_owner, lease_seconds=lease_seconds)
            lease = self._state.resource_leases.get(lease_id)
            if not lease or lease["job_id"] != job_id or lease["lease_owner"] != lease_owner:
                raise RuntimeError(f"resource execution lease is not owned by {lease_owner}: {lease_id}")
            lease["lease_expires_at"] = (
                self._clock.now() + timedelta(seconds=max(30, lease_seconds * 2))
            ).isoformat()
            lease["updated_at"] = iso_now(self._clock)

    def renew_resource_lease(
        self,
        lease_id: str,
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
    ) -> bool:
        with self._state.lock:
            lease = self._state.resource_leases.get(lease_id)
            if not lease or lease["job_id"] != job_id or lease["lease_owner"] != lease_owner:
                return False
            lease["lease_expires_at"] = (
                self._clock.now() + timedelta(seconds=max(30, lease_seconds))
            ).isoformat()
            lease["updated_at"] = iso_now(self._clock)
            return True

    def release_resource_lease(self, lease_id: str, *, job_id: str) -> bool:
        with self._state.lock:
            lease = self._state.resource_leases.get(lease_id)
            if not lease or lease["job_id"] != job_id:
                return False
            del self._state.resource_leases[lease_id]
            return True

    def list_resource_leases(self, project_id: str = "") -> list[dict[str, Any]]:
        with self._state.lock:
            records = list(self._state.resource_leases.values())
            if project_id.strip():
                records = [item for item in records if item["project_id"] == project_id]
            records.sort(key=lambda item: (item["updated_at"], item["lease_id"]))
            return deepcopy(records)

    def health(self) -> dict[str, Any]:
        with self._state.lock:
            active = sum(item["status"] in {"queued", "running", "stopping"} for item in self._state.jobs.values())
            return {
                "ready": True,
                "database": ":memory:",
                "schema_version": 0,
                "job_count": len(self._state.jobs),
                "active_job_count": active,
                "migration_backup": "",
            }

    def _required_job(self, job_id: str) -> dict[str, Any]:
        try:
            return self._state.jobs[job_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Worker job not found: {job_id}") from exc

    def _owned_active_job(self, job_id: str, worker_id: str) -> dict[str, Any]:
        record = self._required_job(job_id)
        if record["lease_owner"] != worker_id or record["status"] not in {"running", "stopping"}:
            raise RuntimeError(f"job lease is not owned by {worker_id}: {job_id}")
        return record

    def _append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        if not event_type or any(char.isspace() for char in event_type):
            raise ValueError(f"invalid event type: {event_type}")
        events = self._state.job_events.setdefault(job_id, [])
        event = {
            "schema": EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "job_id": job_id,
            "event": event_type,
            "at": iso_now(self._clock),
            "data": _redact(deepcopy(data)),
        }
        events.append(event)
        return event

    def _discard_expired_locks(self) -> None:
        now = iso_now(self._clock)
        for key in [key for key, value in self._state.project_locks.items() if value["lease_expires_at"] < now]:
            del self._state.project_locks[key]

    def _discard_expired_resource_leases(self) -> None:
        now = iso_now(self._clock)
        for key in [key for key, value in self._state.resource_leases.items() if value["lease_expires_at"] < now]:
            del self._state.resource_leases[key]


__all__ = ["InMemoryWorkerPersistence"]
