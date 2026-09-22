"""Pure Pi Agent thinking preferences and one-time default migration."""

from __future__ import annotations

from typing import Any


PI_THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
PI_THINKING_KEYS = {"creative": "thinking", "project": "project_agent_thinking"}
_DEFAULTS = {"creative": "medium", "project": "xhigh"}


def get_pi_thinking_preferences(config: dict[str, Any]) -> dict[str, str]:
    runners = config.get("agent_runners")
    settings = runners.get("pi-worker") if isinstance(runners, dict) else None
    settings = settings if isinstance(settings, dict) else {}
    result = {}
    for role, key in PI_THINKING_KEYS.items():
        candidate = str(settings.get(key) or "").strip().lower()
        result[role] = candidate if candidate in PI_THINKING_LEVELS else _DEFAULTS[role]
    return result


def migrate_pi_thinking_preferences(payload: dict[str, Any]) -> dict[str, Any]:
    runners = payload.get("agent_runners")
    settings = runners.get("pi-worker") if isinstance(runners, dict) else None
    if not isinstance(settings, dict) or settings.get("thinking_preferences_version") is not None:
        return payload
    updated = dict(settings)
    if updated.get("thinking") == "low":
        updated["thinking"] = "medium"
    if updated.get("project_agent_thinking") == "max":
        updated["project_agent_thinking"] = "xhigh"
    updated["thinking_preferences_version"] = 1
    return {**payload, "agent_runners": {**runners, "pi-worker": updated}}
