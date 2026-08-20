"""Recoverable in-process supervisor backed by the durable job store."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
import threading
import uuid
from typing import Any, Callable

from .execution_coordinator import ProjectExecutionCoordinator, project_execution_key
from .execution_admission import (
    ExecutionAdmission,
    acquire_execution_admission,
    heartbeat_execution_admission,
    release_execution_admission,
)
from .resources import ResourceClaim
from ..application.persistence_ports import WorkerPersistencePort


class WorkerSupervisor:
    def __init__(
        self,
        store: WorkerPersistencePort,
        *,
        max_workers: int = 2,
        lease_seconds: int = 90,
        execution_coordinator: ProjectExecutionCoordinator | None = None,
    ):
        self.store = store
        self.worker_id = f"studio-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = max(30, int(lease_seconds))
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="les-worker")
        self._futures: dict[str, Future[None]] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self.execution_coordinator = execution_coordinator or ProjectExecutionCoordinator()
        self.recovered_jobs = tuple(self.store.recover_interrupted())

    def submit(
        self,
        job_id: str,
        function: Callable[[threading.Event], dict[str, Any]],
        *,
        lock_key: str,
        resource_claim: ResourceClaim | None = None,
    ) -> None:
        with self._lock:
            existing = self._futures.get(job_id)
            if existing is not None and not existing.done():
                raise RuntimeError(f"job is already supervised: {job_id}")
            cancel_event = threading.Event()
            self._cancel[job_id] = cancel_event
            self._futures[job_id] = self._executor.submit(
                self._run,
                job_id,
                function,
                lock_key,
                cancel_event,
                resource_claim,
            )

    def stop(self, job_id: str) -> dict[str, Any]:
        job = self.store.read(job_id)
        if job["status"] not in {"queued", "running", "stopping", "interrupted"}:
            return job
        with self._lock:
            event = self._cancel.get(job_id)
            if event is not None:
                event.set()
        self.store.append_event(job_id, "run.stop_requested", {})
        return self.store.update(job_id, status="stopping")

    def health(self) -> dict[str, Any]:
        with self._lock:
            active = sorted(job_id for job_id, future in self._futures.items() if not future.done())
        return {
            "ready": True,
            "worker_id": self.worker_id,
            "active_jobs": active,
            "recovered_jobs": list(self.recovered_jobs),
        }

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            for event in self._cancel.values():
                event.set()
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _run(
        self,
        job_id: str,
        function: Callable[[threading.Event], dict[str, Any]],
        lock_key: str,
        cancel_event: threading.Event,
        resource_claim: ResourceClaim | None,
    ) -> None:
        if not self.store.claim(job_id, self.worker_id, lease_seconds=self.lease_seconds):
            return
        project_root = str(self.store.read(job_id).get("request", {}).get("project_root") or "")
        admission, admission_error = self._acquire_admission(
            project_root,
            job_id,
            lock_key,
            resource_claim,
        )
        if admission_error:
            self._finish_unadmitted(job_id, "failed", admission_error)
            return
        if admission is None:
            self._finish_unadmitted(
                job_id,
                "waiting_human",
                "another active task owns the required project resources",
            )
            return
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(admission, heartbeat_stop, cancel_event),
            name=f"les-heartbeat-{job_id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            if cancel_event.is_set():
                self.store.update(job_id, status="cancelled", finished_at=_now_from_store())
                return
            result = function(cancel_event)
            status, result, lease_error = self._normalize_result(result, cancel_event)
            self.store.update(
                job_id,
                status=status,
                result=result,
                error=lease_error,
                finished_at=_now_from_store(),
                lease_owner="",
                lease_expires_at="",
            )
        except Exception as exc:  # durable failure evidence is part of the product contract
            self.store.update(
                job_id,
                status="failed",
                error=str(exc),
                finished_at=_now_from_store(),
                lease_owner="",
                lease_expires_at="",
            )
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)
            try:
                release_execution_admission(
                    self.store,
                    self.execution_coordinator,
                    admission,
                )
            finally:
                with self._lock:
                    self._cancel.pop(job_id, None)

    def _acquire_admission(
        self,
        project_root: str,
        job_id: str,
        lock_key: str,
        resource_claim: ResourceClaim | None,
    ) -> tuple[ExecutionAdmission | None, str]:
        try:
            admission = acquire_execution_admission(
                self.store,
                self.execution_coordinator,
                project_root=project_root,
                job_id=job_id,
                worker_id=self.worker_id,
                lock_key=lock_key,
                lease_seconds=self.lease_seconds,
                resource_claim=resource_claim,
            )
        except (RuntimeError, ValueError) as exc:
            return None, str(exc)
        return admission, ""

    def _finish_unadmitted(self, job_id: str, status: str, error: str) -> None:
        self.store.update(
            job_id,
            status=status,
            error=error,
            finished_at=_now_from_store(),
            lease_owner="",
            lease_expires_at="",
        )

    @staticmethod
    def _normalize_result(
        result: object,
        cancel_event: threading.Event,
    ) -> tuple[str, dict[str, Any], str]:
        if not isinstance(result, dict):
            raise TypeError("supervised worker must return a result object")
        status = str(result.get("status") or "").strip()
        if not status:
            raise ValueError("supervised worker result must declare status")
        lease_error = str(
            getattr(cancel_event, "_arcvellum_execution_lease_error", "")
        )
        if lease_error:
            return "failed", {**result, "status": "failed", "message": lease_error}, lease_error
        if cancel_event.is_set() and status not in {"complete", "route_ready", "waiting_human"}:
            status = "cancelled"
        return status, result, ""

    def _heartbeat_loop(
        self,
        admission: ExecutionAdmission,
        stop: threading.Event,
        cancel_event: threading.Event,
    ) -> None:
        interval = max(5.0, self.lease_seconds / 3)
        while not stop.wait(interval):
            try:
                heartbeat_execution_admission(
                    self.store,
                    admission,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
            except Exception as exc:
                setattr(
                    cancel_event,
                    "_arcvellum_execution_lease_error",
                    f"{type(exc).__name__}: {exc}",
                )
                cancel_event.set()
                return


def project_lock_key(project_root: str | Path, route: str) -> str:
    return f"project:{project_execution_key(project_root)}:execution"


def _now_from_store() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
