"""Minimal application ports owned by the ArcVellum composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class JobStorePort(Protocol):
    def health(self) -> dict[str, Any]: ...


class LiveEventPublisherPort(Protocol):
    def close(self) -> None: ...


class ReadModelCachePort(Protocol):
    def clear(self) -> None: ...


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

    store: JobStorePort
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


__all__ = [
    "ApplicationPorts",
    "ExecutionCoordinatorPort",
    "JobStorePort",
    "LiveEventPublisherPort",
    "ModelConnectionStatusLoader",
    "PreparedContextCachePort",
    "ProcessManagerPort",
    "ReadModelCachePort",
    "RunnerStatusLoader",
    "RuntimePoolPort",
    "WorkerSupervisorPort",
]
