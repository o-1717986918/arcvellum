"""Agent Runner registry."""

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


def agent_runner_status(config: dict[str, object]) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for runtime_id in RUNTIME_TYPES:
        runtime = build_runtime(runtime_id, config)
        availability = runtime.availability()
        capabilities = runtime.capabilities()
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
    return statuses


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
    "runtime_status",
]
