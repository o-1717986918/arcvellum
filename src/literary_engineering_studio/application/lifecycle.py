"""Application lifecycle for durable jobs, events, and Agent Runner sidecars."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
from typing import Any

from .ports import ApplicationPorts


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
    def __init__(self, config: dict[str, Any], ports: ApplicationPorts):
        self.config = config
        self.ports = ports
        self.persistence = ports.persistence
        self.live_events = ports.live_events
        self.read_models = ports.read_models
        self.prepared_context_cache = ports.prepared_context_cache
        self.process_manager = ports.process_manager
        self.opencode_pool = ports.runtime_pool
        self.execution_coordinator = ports.execution_coordinator
        self.supervisor = ports.supervisor
        self._processes: dict[str, ManagedProcessState] = {}
        self._lock = threading.RLock()
        self._runner_states = [
            _pending_runner_state(runner_id, _runner_enabled(config, runner_id))
            for runner_id in ports.runtime_ids
        ]
        self._runner_error = ""
        self._runner_refresh_thread: threading.Thread | None = None
        self._started_at = _now()
        self._closed = False
        self.refresh_agent_runners(wait=False, force=False)

    @property
    def store(self) -> Any:
        """Compatibility view; new use cases depend on named persistence ports."""

        return self.persistence.facade

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

    def start_sidecar(self, spec: Any) -> Any:
        return self.process_manager.start(spec)

    def stop_sidecar(self, component_id: str, *, force: bool = False) -> Any:
        return self.process_manager.stop(component_id, force=force)

    def restart_sidecar(self, component_id: str) -> Any:
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
            "ready": not self._closed and self.persistence.jobs.health()["ready"],
            "started_at": self._started_at,
            "closed": self._closed,
            "job_store": self.persistence.jobs.health(),
            "worker_supervisor": self.supervisor.health(),
            "agent_runners": runner_states,
            "agent_runner_refreshing": runner_refreshing,
            "agent_runner_error": runner_error,
            "model_connections": self.ports.model_connection_status_loader(self.config),
            "opencode_runtime_pool": self.opencode_pool.status(),
            "prepared_context_cache": self.prepared_context_cache.status(),
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
            states = self.ports.runner_status_loader(self.config, force_refresh=force)
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
        self.prepared_context_cache.clear()
        self.process_manager.shutdown()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pending_runner_state(runner_id: str, enabled: bool) -> dict[str, Any]:
    return {
        "runtime": runner_id,
        "runner_id": runner_id,
        "registered": True,
        "enabled": enabled,
        "probed": False,
        "available": False,
        "installed": False,
        "readiness_state": "checking" if enabled else "unavailable",
        "executable": "",
        "detail": "正在后台检查本机创作执行器。" if enabled else "disabled by configuration",
        "capabilities": {
            "runner_id": runner_id,
            "available": False,
            "readiness_state": "checking" if enabled else "unavailable",
        },
    }


def _runner_enabled(config: dict[str, Any], runner_id: str) -> bool:
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    settings = runners.get(runner_id) if isinstance(runners.get(runner_id), dict) else {}
    return settings.get("enabled") is not False
