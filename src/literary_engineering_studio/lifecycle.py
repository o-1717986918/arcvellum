"""Application lifecycle for durable jobs, events, and Agent Runner sidecars."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any

from .jobs import JobStore
from .execution_coordinator import ProjectExecutionCoordinator
from .live_events import LiveEventBus
from .model_connections import model_connection_status
from .opencode_runtime_pool import OpenCodeRuntimePool
from .process_manager import ProcessManager, ProcessRecord, ProcessSpec
from .read_model_cache import ReadModelCache
from .runtimes import RUNTIME_TYPES, agent_runner_status
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
        self.live_events = LiveEventBus()
        self.read_models = ReadModelCache()
        self.process_manager = ProcessManager(data_root / "logs" / "sidecars")
        self.opencode_pool = OpenCodeRuntimePool(config, self.process_manager)
        self.execution_coordinator = ProjectExecutionCoordinator()
        self.supervisor = WorkerSupervisor(
            self.store,
            max_workers=int(application.get("max_workers") or 2),
            lease_seconds=int(application.get("lease_seconds") or 90),
            execution_coordinator=self.execution_coordinator,
        )
        self._processes: dict[str, ManagedProcessState] = {}
        self._lock = threading.RLock()
        self._runner_states = [_pending_runner_state(runner_id) for runner_id in RUNTIME_TYPES]
        self._runner_error = ""
        self._runner_refresh_thread: threading.Thread | None = None
        self._started_at = _now()
        self._closed = False
        self.refresh_agent_runners(wait=False, force=False)

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
            runner_states = deepcopy(self._runner_states)
            runner_refreshing = bool(
                self._runner_refresh_thread is not None and self._runner_refresh_thread.is_alive()
            )
            runner_error = self._runner_error
        processes.extend(self.process_manager.status())
        return {
            "ready": not self._closed and self.store.health()["ready"],
            "started_at": self._started_at,
            "closed": self._closed,
            "job_store": self.store.health(),
            "worker_supervisor": self.supervisor.health(),
            "agent_runners": runner_states,
            "agent_runner_refreshing": runner_refreshing,
            "agent_runner_error": runner_error,
            "model_connections": model_connection_status(self.config),
            "opencode_runtime_pool": self.opencode_pool.status(),
            "managed_processes": processes,
        }

    def refresh_agent_runners(
        self,
        *,
        wait: bool = False,
        force: bool = True,
    ) -> list[dict[str, Any]]:
        """Refresh slow executable probes without putting them on the health-check path."""
        with self._lock:
            thread = self._runner_refresh_thread
            if thread is None or not thread.is_alive():
                thread = threading.Thread(
                    target=self._load_agent_runner_states,
                    args=(force,),
                    name="arcvellum-runner-status",
                    daemon=True,
                )
                self._runner_refresh_thread = thread
                thread.start()
        if wait:
            thread.join()
        with self._lock:
            return deepcopy(self._runner_states)

    def _load_agent_runner_states(self, force: bool) -> None:
        try:
            states = agent_runner_status(self.config, force_refresh=force)
            error = ""
        except Exception as exc:
            states = []
            error = str(exc)
        with self._lock:
            if not self._closed and states:
                self._runner_states = deepcopy(states)
            self._runner_error = error

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.supervisor.shutdown(wait=wait)
        self.opencode_pool.shutdown()
        self.live_events.close()
        self.read_models.clear()
        self.process_manager.shutdown()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pending_runner_state(runner_id: str) -> dict[str, Any]:
    return {
        "runtime": runner_id,
        "runner_id": runner_id,
        "available": False,
        "installed": False,
        "readiness_state": "checking",
        "executable": "",
        "detail": "正在后台检查本机创作执行器。",
        "capabilities": {
            "runner_id": runner_id,
            "available": False,
            "readiness_state": "checking",
        },
    }
