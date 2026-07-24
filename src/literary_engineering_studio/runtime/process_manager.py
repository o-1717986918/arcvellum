"""Managed sidecar processes with explicit readiness and shutdown behavior."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Mapping, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProcessSpec:
    component_id: str
    kind: str
    command: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str]
    readiness_url: str = ""
    readiness_headers: Mapping[str, str] | None = None
    readiness_timeout: float = 20.0
    graceful_timeout: float = 8.0


@dataclass
class ProcessRecord:
    component_id: str
    kind: str
    state: str
    pid: int | None
    command: tuple[str, ...]
    cwd: str
    readiness_url: str
    log_path: str
    started_at: str
    updated_at: str
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["command"] = list(self.command)
        return payload


class ProcessManager:
    def __init__(self, log_root: Path):
        self.log_root = log_root.expanduser().resolve()
        self.log_root.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._records: dict[str, ProcessRecord] = {}
        self._logs: dict[str, object] = {}
        self._specs: dict[str, ProcessSpec] = {}
        self._lock = threading.RLock()

    def start(self, spec: ProcessSpec) -> ProcessRecord:
        self._validate_spec(spec)
        with self._lock:
            existing = self._processes.get(spec.component_id)
            if existing is not None and existing.poll() is None:
                raise RuntimeError(f"managed process is already running: {spec.component_id}")
            log_path = self.log_root / f"{spec.component_id}.log"
            log_handle = log_path.open("a", encoding="utf-8")
            environment = os.environ.copy()
            environment.update({str(key): str(value) for key, value in spec.environment.items()})
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                process = subprocess.Popen(
                    list(spec.command),
                    cwd=spec.cwd,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                    creationflags=creationflags,
                )
            except Exception:
                log_handle.close()
                raise
            now = _now()
            record = ProcessRecord(
                component_id=spec.component_id,
                kind=spec.kind,
                state="starting",
                pid=process.pid,
                command=spec.command,
                cwd=str(spec.cwd),
                readiness_url=spec.readiness_url,
                log_path=str(log_path),
                started_at=now,
                updated_at=now,
            )
            self._processes[spec.component_id] = process
            self._records[spec.component_id] = record
            self._logs[spec.component_id] = log_handle
            self._specs[spec.component_id] = spec
        try:
            self._wait_until_ready(spec, process)
        except Exception as exc:
            with self._lock:
                record.state = "failed"
                record.detail = str(exc)
                record.updated_at = _now()
            self.stop(spec.component_id, force=True)
            raise
        with self._lock:
            record.state = "ready"
            record.detail = "readiness probe passed" if spec.readiness_url else "process is running"
            record.updated_at = _now()
            return record

    def stop(self, component_id: str, *, force: bool = False) -> ProcessRecord | None:
        with self._lock:
            process = self._processes.get(component_id)
            record = self._records.get(component_id)
            spec = self._specs.get(component_id)
        if process is None or record is None:
            return None
        record.state = "stopping"
        record.updated_at = _now()
        if process.poll() is None:
            if force:
                process.kill()
            else:
                process.terminate()
                try:
                    process.wait(timeout=spec.graceful_timeout if spec else 8.0)
                except subprocess.TimeoutExpired:
                    process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        with self._lock:
            record.state = "stopped"
            record.updated_at = _now()
            record.detail = f"exit code {process.poll()}"
            record.pid = None
            log_handle = self._logs.pop(component_id, None)
            if log_handle is not None:
                log_handle.close()
            self._processes.pop(component_id, None)
            return record

    def restart(self, component_id: str) -> ProcessRecord:
        with self._lock:
            spec = self._specs.get(component_id)
        if spec is None:
            raise FileNotFoundError(f"managed process specification not found: {component_id}")
        self.stop(component_id)
        return self.start(spec)

    def status(self) -> list[dict[str, object]]:
        with self._lock:
            for component_id, process in list(self._processes.items()):
                if process.poll() is not None:
                    record = self._records[component_id]
                    record.state = "exited"
                    record.pid = None
                    record.detail = f"exit code {process.returncode}"
                    record.updated_at = _now()
            return [self._records[key].as_dict() for key in sorted(self._records)]

    def shutdown(self) -> None:
        with self._lock:
            component_ids = list(self._processes)
        for component_id in reversed(component_ids):
            self.stop(component_id)

    def _wait_until_ready(self, spec: ProcessSpec, process: subprocess.Popen[str]) -> None:
        if not spec.readiness_url:
            time.sleep(0.05)
            if process.poll() is not None:
                raise RuntimeError(f"process exited during startup with {process.returncode}")
            return
        deadline = time.monotonic() + max(1.0, spec.readiness_timeout)
        last_error = ""
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"process exited before readiness with {process.returncode}")
            try:
                headers = {"Accept": "application/json"}
                headers.update({str(key): str(value) for key, value in (spec.readiness_headers or {}).items()})
                request = Request(spec.readiness_url, headers=headers)
                with urlopen(request, timeout=1.0) as response:
                    if 200 <= response.status < 300:
                        body = response.read(4096)
                        if body:
                            try:
                                payload = json.loads(body.decode("utf-8"))
                                if isinstance(payload, dict) and payload.get("ok") is False:
                                    raise RuntimeError("readiness endpoint reported not ready")
                            except json.JSONDecodeError:
                                pass
                        return
            except (OSError, URLError, RuntimeError) as exc:
                last_error = str(exc)
            time.sleep(0.15)
        raise TimeoutError(f"readiness timed out for {spec.component_id}: {last_error}")

    @staticmethod
    def _validate_spec(spec: ProcessSpec) -> None:
        if not spec.component_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in spec.component_id):
            raise ValueError(f"invalid managed process id: {spec.component_id}")
        if not spec.command or not str(spec.command[0]).strip():
            raise ValueError("managed process command must not be empty")
        if not spec.cwd.is_dir():
            raise FileNotFoundError(f"managed process cwd not found: {spec.cwd}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
