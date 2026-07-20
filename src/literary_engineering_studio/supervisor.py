"""Recoverable in-process supervisor backed by the durable job store."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import hashlib
from pathlib import Path
import threading
import uuid
from typing import Any, Callable

from .jobs import JobStore


class WorkerSupervisor:
    def __init__(self, store: JobStore, *, max_workers: int = 2, lease_seconds: int = 90):
        self.store = store
        self.worker_id = f"studio-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = max(30, int(lease_seconds))
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="les-worker")
        self._futures: dict[str, Future[None]] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self.recovered_jobs = tuple(self.store.recover_interrupted())

    def submit(
        self,
        job_id: str,
        function: Callable[[threading.Event], dict[str, Any]],
        *,
        lock_key: str,
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
    ) -> None:
        if not self.store.claim(job_id, self.worker_id, lease_seconds=self.lease_seconds):
            return
        if not self.store.acquire_lock(lock_key, job_id, self.worker_id, lease_seconds=self.lease_seconds * 2):
            self.store.update(
                job_id,
                status="waiting_human",
                error="another active task owns this project route",
                finished_at=_now_from_store(),
                lease_owner="",
                lease_expires_at="",
            )
            return
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job_id, heartbeat_stop),
            name=f"les-heartbeat-{job_id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            if cancel_event.is_set():
                self.store.update(job_id, status="cancelled", finished_at=_now_from_store())
                return
            result = function(cancel_event)
            status = str(result.get("status") or "complete")
            if cancel_event.is_set() and status not in {"complete", "route_ready", "waiting_human"}:
                status = "cancelled"
            self.store.update(
                job_id,
                status=status,
                result=result,
                error="",
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
            self.store.release_lock(lock_key, job_id)
            with self._lock:
                self._cancel.pop(job_id, None)

    def _heartbeat_loop(self, job_id: str, stop: threading.Event) -> None:
        interval = max(5.0, self.lease_seconds / 3)
        while not stop.wait(interval):
            try:
                self.store.heartbeat(job_id, self.worker_id, lease_seconds=self.lease_seconds)
            except (FileNotFoundError, RuntimeError):
                return


def project_lock_key(project_root: str | Path, route: str) -> str:
    project = str(Path(project_root).expanduser().resolve()).casefold()
    digest = hashlib.sha256(project.encode("utf-8")).hexdigest()[:20]
    return f"project:{digest}:route:{str(route or 'auto').strip().lower()}"


def _now_from_store() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
