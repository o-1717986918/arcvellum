"""Minimal application ports owned by the ArcVellum composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .persistence_ports import PersistencePorts


class LiveEventPublisherPort(Protocol):
    def publish(self, channel: str, event: str, data: dict[str, Any]) -> Any: ...

    def wait_since(
        self,
        channel: str,
        after: int,
        *,
        timeout: float = 0.5,
    ) -> list[dict[str, Any]]: ...

    def close(self) -> None: ...


class ReadModelCachePort(Protocol):
    def get(self, key: str, project_root: Any, builder: Callable[[], Any]) -> Any: ...

    def invalidate(self, project_root: Any, reason: str = "project-mutated") -> int: ...

    def revision(self, project_root: Any) -> int: ...

    def clear(self, project_root: Any | None = None) -> None: ...


class PreparedContextCachePort(Protocol):
    def status(self) -> dict[str, object]: ...

    def clear(self) -> None: ...


class ProcessManagerPort(Protocol):
    def start(self, spec: Any) -> Any: ...

    def stop(self, component_id: str, *, force: bool = False) -> Any: ...

    def restart(self, component_id: str) -> Any: ...

    def status(self) -> list[dict[str, object]]: ...

    def shutdown(self) -> None: ...


class RuntimePoolPort(Protocol):
    def status(self) -> dict[str, Any]: ...

    def shutdown(self) -> None: ...


class WorkerSupervisorPort(Protocol):
    def health(self) -> dict[str, Any]: ...

    def shutdown(self, *, wait: bool = True) -> None: ...


class ExecutionCoordinatorPort(Protocol):
    def acquire(self, project_root: Any, owner: str) -> bool: ...

    def release(self, project_root: Any, owner: str) -> None: ...


RunnerStatusLoader = Callable[..., list[dict[str, object]]]
ModelConnectionStatusLoader = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ApplicationPorts:
    """One application's replaceable infrastructure and process boundaries."""

    persistence: PersistencePorts
    live_events: LiveEventPublisherPort
    read_models: ReadModelCachePort
    prepared_context_cache: PreparedContextCachePort
    process_manager: ProcessManagerPort
    runtime_pool: RuntimePoolPort
    execution_coordinator: ExecutionCoordinatorPort
    supervisor: WorkerSupervisorPort
    runtime_ids: tuple[str, ...]
    runner_status_loader: RunnerStatusLoader
    model_connection_status_loader: ModelConnectionStatusLoader

    @property
    def store(self) -> Any:
        """Compatibility seam while use cases migrate to named repositories."""

        return self.persistence.facade


__all__ = [
    "ApplicationPorts",
    "ExecutionCoordinatorPort",
    "LiveEventPublisherPort",
    "ModelConnectionStatusLoader",
    "PreparedContextCachePort",
    "ProcessManagerPort",
    "ReadModelCachePort",
    "RunnerStatusLoader",
    "RuntimePoolPort",
    "WorkerSupervisorPort",
]
