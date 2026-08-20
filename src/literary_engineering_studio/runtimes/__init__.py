"""Agent Runner registry."""

from __future__ import annotations

from copy import deepcopy
import json
import threading
import time

from .base import (
    AgentRunnerCapabilities,
    AgentRuntime,
    AgentRuntimePort,
    RuntimeAvailability,
    RuntimeResult,
    SubprocessRuntimeBase,
)
from .claude_code import ClaudeCodeRuntime
from .codex_cli import CodexCliRuntime
from .host_agent import HostAgentRuntime
from .opencode import OpenCodeRuntime
from .pi_rpc import PiRpcRuntime
from .pi_worker import PiWorkerRuntime
from .registry import (
    RuntimeDescriptor,
    RuntimeFactoryContext,
    RuntimeRegistry,
    runtime_descriptor,
)


def _opencode_factory(
    settings: dict[str, object],
    context: RuntimeFactoryContext,
) -> AgentRuntimePort:
    runtime = OpenCodeRuntime(settings)
    runtime.runtime_pool = context.runtime_pool
    return runtime


DEFAULT_RUNTIME_REGISTRY = RuntimeRegistry(
    (
        runtime_descriptor(OpenCodeRuntime, _opencode_factory),
        runtime_descriptor(HostAgentRuntime),
        runtime_descriptor(ClaudeCodeRuntime),
        runtime_descriptor(CodexCliRuntime),
        runtime_descriptor(PiRpcRuntime),
        runtime_descriptor(PiWorkerRuntime),
    )
)

# Compatibility snapshot. New composition code consumes DEFAULT_RUNTIME_REGISTRY.
RUNTIME_TYPES = DEFAULT_RUNTIME_REGISTRY.runtime_types()

_STATUS_CACHE: dict[str, tuple[float, list[dict[str, object]]]] = {}
_STATUS_LOCK = threading.RLock()
_STATUS_TTL_SECONDS = 30.0


def build_runtime(
    runtime_id: str,
    config: dict[str, object],
    *,
    runtime_pool=None,
    role: str | None = None,
    registry: RuntimeRegistry = DEFAULT_RUNTIME_REGISTRY,
) -> AgentRuntimePort:
    normalized = str(runtime_id or "").strip().lower()
    descriptor = registry.descriptor(normalized)
    settings = _runtime_settings(config, normalized)
    if settings.get("enabled") is False:
        raise RuntimeError(f"Agent runtime is disabled: {normalized}")
    if settings.get("experiment_only") is True and settings.get("experiment_authorized") is not True:
        raise RuntimeError(f"Agent runtime requires an explicit experimental invocation: {normalized}")
    return descriptor.create(
        settings,
        RuntimeFactoryContext(runtime_pool=runtime_pool, role=role),
    )


def agent_runner_status(
    config: dict[str, object],
    *,
    force_refresh: bool = False,
    max_age_seconds: float = _STATUS_TTL_SECONDS,
    registry: RuntimeRegistry = DEFAULT_RUNTIME_REGISTRY,
) -> list[dict[str, object]]:
    cache_key = _status_cache_key(config, registry)
    now = time.monotonic()
    with _STATUS_LOCK:
        cached = _STATUS_CACHE.get(cache_key)
        if cached and not force_refresh and now - cached[0] <= max(0.0, max_age_seconds):
            return deepcopy(cached[1])
    statuses: list[dict[str, object]] = []
    for runtime_id in registry.ids():
        settings = _runtime_settings(config, runtime_id)
        enabled = settings.get("enabled") is not False
        authorized = settings.get("experiment_only") is not True or settings.get("experiment_authorized") is True
        should_probe = enabled and authorized
        runtime = registry.create(runtime_id, settings)
        availability = (
            runtime.availability()
            if should_probe
            else RuntimeAvailability(
                runtime_id,
                False,
                str(settings.get("executable") or ""),
                "disabled by configuration" if not enabled else "experimental invocation required",
            )
        )
        capabilities = runtime.capabilities(availability)
        statuses.append(
            {
                "runtime": availability.runtime,
                "runner_id": capabilities.runner_id,
                "registered": True,
                "enabled": enabled,
                "probed": should_probe,
                "available": capabilities.available,
                "installed": availability.available,
                "readiness_state": capabilities.readiness_state,
                "executable": availability.executable,
                "detail": availability.detail,
                "capabilities": capabilities.as_dict(),
            }
        )
    with _STATUS_LOCK:
        _STATUS_CACHE[cache_key] = (time.monotonic(), deepcopy(statuses))
    return statuses


def clear_agent_runner_status_cache() -> None:
    with _STATUS_LOCK:
        _STATUS_CACHE.clear()


def _status_cache_key(
    config: dict[str, object], registry: RuntimeRegistry
) -> str:
    runners = config.get("agent_runners", {}) if isinstance(config.get("agent_runners"), dict) else {}
    return registry.cache_key() + ":" + json.dumps(
        runners, ensure_ascii=False, sort_keys=True, default=str
    )


def _runtime_settings(config: dict[str, object], runtime_id: str) -> dict[str, object]:
    runners = config.get("agent_runners", {}) if isinstance(config.get("agent_runners"), dict) else {}
    if not runners and isinstance(config.get("runtimes"), dict):
        runners = config["runtimes"]
    value = runners.get(runtime_id)
    return dict(value) if isinstance(value, dict) else {}


def runtime_status(config: dict[str, object]) -> list[dict[str, object]]:
    """Compatibility alias for the v0.2 API."""
    return agent_runner_status(config)


__all__ = [
    "AgentRuntime",
    "AgentRuntimePort",
    "AgentRunnerCapabilities",
    "DEFAULT_RUNTIME_REGISTRY",
    "RuntimeDescriptor",
    "RuntimeFactoryContext",
    "RuntimeRegistry",
    "RuntimeAvailability",
    "RuntimeResult",
    "SubprocessRuntimeBase",
    "build_runtime",
    "agent_runner_status",
    "clear_agent_runner_status_cache",
    "runtime_status",
]
