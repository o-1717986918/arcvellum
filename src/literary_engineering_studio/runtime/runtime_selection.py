"""Central runtime selection policy for creative application roles."""

from __future__ import annotations

from typing import Any


DEFAULT_CREATIVE_RUNTIME = "pi-worker"


def runtime_for_role(config: dict[str, Any], role: str) -> str:
    """Resolve one role without coupling callers to a concrete runner config."""

    roles = config.get("agent_runtime_roles")
    values = roles if isinstance(roles, dict) else {}
    return str(values.get(role) or DEFAULT_CREATIVE_RUNTIME).strip().lower()


__all__ = ["DEFAULT_CREATIVE_RUNTIME", "runtime_for_role"]
