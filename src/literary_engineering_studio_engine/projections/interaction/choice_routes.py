"""Route-local workflow facts used to discover human choices."""

from __future__ import annotations

from pathlib import Path

from ...workflow.state import project_workflow_state
from ...workflow_state import next_scene_workflow_state


def route_choice_actions(
    root: Path,
    route: str,
    *,
    project_state=project_workflow_state,
    next_scene_state=next_scene_workflow_state,
) -> tuple[list[dict[str, object]], str]:
    if route == "scene-development":
        return _scene_action(root, route, next_scene_state)
    payload = project_state(root, route=route)
    items = _state_items(payload, route)
    return [_action_from_state(route, item) for item in items], f"workflow/runtime_choices/{route}.json"


def _scene_action(root: Path, route: str, next_scene_state) -> tuple[list[dict[str, object]], str]:
    state = next_scene_state(root)
    if not state or state.get("status") == "ready":
        return [], ""
    return [{
        "route": route,
        "target": state.get("scene_id", ""),
        "current_step": state.get("current_step", ""),
        "next_action": state.get("next_action", ""),
    }], ""


def _state_items(payload: dict[str, object], route: str) -> list[dict[str, object]]:
    keys = {
        "longform-planning": ("longform",),
        "source-ingest": ("source_ingests",),
        "style-engineering": ("styles",),
        "character-and-world-assets": ("assets",),
        "review-and-audit": ("audits",),
        "export-and-release": ("exports",),
    }.get(route, ())
    items: list[dict[str, object]] = []
    for key in keys:
        value = payload.get(key)
        candidates = [value] if isinstance(value, dict) else value if isinstance(value, list) else []
        items.extend(item for item in candidates if isinstance(item, dict) and item.get("status") != "ready")
    return items


def _action_from_state(route: str, item: dict[str, object]) -> dict[str, object]:
    candidate_id = str(item.get("candidate_id") or "")
    return {
        "route": route,
        "target": candidate_id or item.get("scene_id") or item.get("target_id") or "",
        "current_step": item.get("current_step", ""),
        "next_action": item.get("next_action", ""),
    }


__all__ = ["route_choice_actions"]
