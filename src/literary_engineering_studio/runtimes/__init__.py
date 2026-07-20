"""Agent Runner registry."""

from __future__ import annotations

from copy import deepcopy
import json
import threading
import time

from .base import AgentRunnerCapabilities, AgentRuntime, RuntimeAvailability, RuntimeResult
from .claude_code import ClaudeCodeRuntime
from .codex_cli import CodexCliRuntime
from .host_agent import HostAgentRuntime
from .opencode import OpenCodeRuntime


RUNTIME_TYPES = {
    "opencode": OpenCodeRuntime,
    "host-agent": HostAgentRuntime,
    "claude-code": ClaudeCodeRuntime,
    "codex-cli": CodexCliRuntime,
}

_STATUS_CACHE: dict[str, tuple[float, list[dict[str, object]]]] = {}
_STATUS_LOCK = threading.RLock()
_STATUS_TTL_SECONDS = 30.0


def build_runtime(runtime_id: str, config: dict[str, object]) -> AgentRuntime:
    normalized = str(runtime_id or "").strip().lower()
    runtime_type = RUNTIME_TYPES.get(normalized)
    if runtime_type is None:
        raise ValueError(f"unknown Agent runtime: {runtime_id}")
    runners = config.get("agent_runners", {}) if isinstance(config.get("agent_runners"), dict) else {}
    if not runners and isinstance(config.get("runtimes"), dict):
        runners = config["runtimes"]
    settings = runners.get(normalized, {}) if isinstance(runners.get(normalized), dict) else {}
    if settings.get("enabled") is False:
        raise RuntimeError(f"Agent runtime is disabled: {normalized}")
    return runtime_type(settings)


def agent_runner_status(
    config: dict[str, object],
    *,
    force_refresh: bool = False,
    max_age_seconds: float = _STATUS_TTL_SECONDS,
) -> list[dict[str, object]]:
    cache_key = _status_cache_key(config)
    now = time.monotonic()
    with _STATUS_LOCK:
        cached = _STATUS_CACHE.get(cache_key)
        if cached and not force_refresh and now - cached[0] <= max(0.0, max_age_seconds):
            return deepcopy(cached[1])
    statuses: list[dict[str, object]] = []
    for runtime_id in RUNTIME_TYPES:
        runtime = build_runtime(runtime_id, config)
        availability = runtime.availability()
        capabilities = runtime.capabilities(availability)
        statuses.append(
            {
                "runtime": availability.runtime,
                "runner_id": capabilities.runner_id,
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


def _status_cache_key(config: dict[str, object]) -> str:
    runners = config.get("agent_runners", {}) if isinstance(config.get("agent_runners"), dict) else {}
    return json.dumps(runners, ensure_ascii=False, sort_keys=True, default=str)


def runtime_status(config: dict[str, object]) -> list[dict[str, object]]:
    """Compatibility alias for the v0.2 API."""
    return agent_runner_status(config)


__all__ = [
    "AgentRuntime",
    "AgentRunnerCapabilities",
    "RuntimeAvailability",
    "RuntimeResult",
    "build_runtime",
    "agent_runner_status",
    "clear_agent_runner_status_cache",
    "runtime_status",
]
