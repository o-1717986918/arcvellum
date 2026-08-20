"""Default desktop/server adapter assembly for one application instance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..application.ports import ApplicationPorts
from ..integrations.model_connections import model_connection_status
from ..integrations.opencode.opencode_runtime_pool import OpenCodeRuntimePool
from ..observability.live_events import LiveEventBus
from ..persistence.job_store import JobStore
from ..persistence.composition import sqlite_persistence_ports
from ..projections.read_model_cache import ReadModelCache
from ..runtime.execution_coordinator import ProjectExecutionCoordinator
from ..runtime.prepared_context_cache import PreparedContextCache
from ..runtime.process_manager import ProcessManager
from ..runtime.supervisor import WorkerSupervisor
from ..runtimes import DEFAULT_RUNTIME_REGISTRY, agent_runner_status


def build_default_application_ports(config: dict[str, Any]) -> ApplicationPorts:
    """Build fresh adapters; no process, cache, or store is shared across apps."""

    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    database = Path(str(application.get("database_path") or "studio.sqlite3"))
    data_root = Path(str(application.get("data_root") or database.parent)).expanduser().resolve()
    worker = config.get("worker") if isinstance(config.get("worker"), dict) else {}
    cache = worker.get("prepared_context_cache") if isinstance(worker.get("prepared_context_cache"), dict) else {}

    store = JobStore(database)
    persistence = sqlite_persistence_ports(store)
    process_manager = ProcessManager(data_root / "logs" / "sidecars")
    execution_coordinator = ProjectExecutionCoordinator()
    return ApplicationPorts(
        persistence=persistence,
        live_events=LiveEventBus(),
        read_models=ReadModelCache(),
        prepared_context_cache=PreparedContextCache(
            enabled=bool(cache.get("enabled", False)),
            max_entries=int(cache.get("max_entries") or 32),
            routes=tuple(str(item) for item in cache.get("routes") or []),
            states=tuple(str(item) for item in cache.get("states") or []),
        ),
        process_manager=process_manager,
        runtime_pool=OpenCodeRuntimePool(config, process_manager),
        execution_coordinator=execution_coordinator,
        supervisor=WorkerSupervisor(
            persistence.worker,
            max_workers=int(application.get("max_workers") or 2),
            lease_seconds=int(application.get("lease_seconds") or 90),
            execution_coordinator=execution_coordinator,
        ),
        runtime_ids=DEFAULT_RUNTIME_REGISTRY.ids(),
        runner_status_loader=agent_runner_status,
        model_connection_status_loader=model_connection_status,
    )


__all__ = ["build_default_application_ports"]
