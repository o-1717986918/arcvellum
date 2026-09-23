"""Local policy for optional scene performance material calls."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


def get_scene_performance_preferences(config: dict[str, Any]) -> dict[str, Any]:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    settings = application.get("scene_performance_agents")
    values = settings if isinstance(settings, dict) else {}
    try:
        limit = int(values.get("max_actor_calls", 4))
    except (TypeError, ValueError):
        limit = 4
    return {"enabled": values.get("enabled") is True, "max_actor_calls": max(0, min(4, limit))}


def set_scene_performance_preferences(
    config: dict[str, Any], enabled: bool, max_actor_calls: int,
    *, save: Callable[[dict[str, Any], Path | None], Path], path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(enabled, bool) or isinstance(max_actor_calls, bool) or not isinstance(max_actor_calls, int):
        raise ValueError("scene performance preferences require a boolean and integer")
    if not 0 <= max_actor_calls <= 4:
        raise ValueError("max_actor_calls must be between 0 and 4")
    values = {"enabled": enabled, "max_actor_calls": max_actor_calls}
    proposed = deepcopy(config)
    proposed.setdefault("application", {})["scene_performance_agents"] = values
    save(proposed, path)
    config.setdefault("application", {})["scene_performance_agents"] = values
    return values


__all__ = ["get_scene_performance_preferences", "set_scene_performance_preferences"]
