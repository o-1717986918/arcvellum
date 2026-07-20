"""Application lifecycle for durable jobs, events, and Agent Runner sidecars."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any

from .jobs import JobStore
from .model_connections import model_connection_status
from .process_manager import ProcessManager, ProcessRecord, ProcessSpec
from .runtimes import agent_runner_status
from .supervisor import WorkerSupervisor


@dataclass(frozen=True)
class ManagedProcessState:
    component_id: str
    kind: str
    state: str
    pid: int | None = None
    version: str = ""
    endpoint: str = ""
    detail: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApplicationLifecycleManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        application = config.get("application", {}) if isinstance(config.get("application"), dict) else {}
        database = Path(str(application.get("database_path") or "studio.sqlite3"))
        data_root = Path(str(application.get("data_root") or database.parent)).expanduser().resolve()
        self.store = JobStore(database)
        self.process_manager = ProcessManager(data_root / "logs" / "sidecars")
        self.supervisor = WorkerSupervisor(
            self.store,
            max_workers=int(application.get("max_workers") or 2),
            lease_seconds=int(application.get("lease_seconds") or 90),
        )
        self._processes: dict[str, ManagedProcessState] = {}
        self._lock = threading.RLock()
        self._started_at = _now()
        self._closed = False

    def register_process(self, state: ManagedProcessState) -> None:
        if not state.component_id.strip():
            raise ValueError("managed process component id must not be empty")
        with self._lock:
            self._processes[state.component_id] = state

    def unregister_process(self, component_id: str, *, detail: str = "stopped") -> None:
        with self._lock:
            previous = self._processes.get(component_id)
            if previous is None:
                return
            self._processes[component_id] = ManagedProcessState(
                component_id=previous.component_id,
                kind=previous.kind,
                state="stopped",
                version=previous.version,
                endpoint=previous.endpoint,
                detail=detail,
                updated_at=_now(),
            )

    def start_sidecar(self, spec: ProcessSpec) -> ProcessRecord:
        return self.process_manager.start(spec)

    def stop_sidecar(self, component_id: str, *, force: bool = False) -> ProcessRecord | None:
        return self.process_manager.stop(component_id, force=force)

    def restart_sidecar(self, component_id: str) -> ProcessRecord:
        return self.process_manager.restart(component_id)

    def health(self) -> dict[str, Any]:
        with self._lock:
            processes = [item.as_dict() for item in self._processes.values()]
        processes.extend(self.process_manager.status())
        runner_states: list[dict[str, Any]]
        try:
            runner_states = agent_runner_status(self.config)
        except Exception as exc:
            runner_states = [{"available": False, "detail": str(exc)}]
        return {
            "ready": not self._closed and self.store.health()["ready"],
            "started_at": self._started_at,
            "closed": self._closed,
            "job_store": self.store.health(),
            "worker_supervisor": self.supervisor.health(),
            "agent_runners": runner_states,
            "model_connections": model_connection_status(self.config),
            "managed_processes": processes,
        }

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.process_manager.shutdown()
        self.supervisor.shutdown(wait=wait)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
