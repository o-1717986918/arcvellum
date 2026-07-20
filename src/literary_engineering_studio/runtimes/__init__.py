"""Runtime registry."""

from .base import AgentRuntime, RuntimeAvailability, RuntimeResult
from .claude_code import ClaudeCodeRuntime
from .codex_cli import CodexCliRuntime
from .host_agent import HostAgentRuntime


RUNTIME_TYPES = {
    "host-agent": HostAgentRuntime,
    "claude-code": ClaudeCodeRuntime,
    "codex-cli": CodexCliRuntime,
}


def build_runtime(runtime_id: str, config: dict[str, object]) -> AgentRuntime:
    normalized = str(runtime_id or "").strip().lower()
    runtime_type = RUNTIME_TYPES.get(normalized)
    if runtime_type is None:
        raise ValueError(f"unknown Agent runtime: {runtime_id}")
    runtimes = config.get("runtimes", {}) if isinstance(config.get("runtimes"), dict) else {}
    settings = runtimes.get(normalized, {}) if isinstance(runtimes.get(normalized), dict) else {}
    if settings.get("enabled") is False:
        raise RuntimeError(f"Agent runtime is disabled: {normalized}")
    return runtime_type(settings)


def runtime_status(config: dict[str, object]) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for runtime_id in RUNTIME_TYPES:
        runtime = build_runtime(runtime_id, config)
        availability = runtime.availability()
        statuses.append(
            {
                "runtime": availability.runtime,
                "available": availability.available,
                "executable": availability.executable,
                "detail": availability.detail,
            }
        )
    return statuses


__all__ = [
    "AgentRuntime",
    "RuntimeAvailability",
    "RuntimeResult",
    "build_runtime",
    "runtime_status",
]
