"""Small persistent background-job registry for Agent Worker runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
from typing import Any, Callable


JOB_SCHEMA = "literary-engineering-studio/worker-job/v0.1"


class JobStore:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = f"job-{uuid.uuid4().hex[:16]}"
        payload = {
            "schema": JOB_SCHEMA,
            "job_id": job_id,
            "status": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "request": request,
            "result": {},
            "error": "",
        }
        self._write(payload)
        return payload

    def read(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"Worker job not found: {job_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"invalid worker job: {path}")
        return payload

    def update(self, job_id: str, **updates: object) -> dict[str, Any]:
        with self._lock:
            payload = self.read(job_id)
            payload.update(updates)
            payload["updated_at"] = _now()
            self._write(payload)
        return payload

    def start(self, job_id: str, function: Callable[[], dict[str, Any]]) -> None:
        def target() -> None:
            self.update(job_id, status="running", started_at=_now())
            try:
                result = function()
            except Exception as exc:  # worker errors must remain inspectable by the UI
                self.update(job_id, status="failed", error=str(exc), finished_at=_now())
                return
            final_status = str(result.get("status") or "complete")
            self.update(job_id, status=final_status, result=result, finished_at=_now())

        thread = threading.Thread(target=target, name=f"les-{job_id}", daemon=True)
        thread.start()

    def _path(self, job_id: str) -> Path:
        if not job_id.startswith("job-") or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in job_id):
            raise ValueError(f"invalid worker job id: {job_id}")
        return self.root / f"{job_id}.json"

    def _write(self, payload: dict[str, Any]) -> None:
        path = self._path(str(payload["job_id"]))
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

