"""Render the machine-bound creative-plan fragment exposed to a task Agent."""

from __future__ import annotations

from typing import Any


def creative_plan_task_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": str(payload.get("creative_plan_id") or ""),
        "revision": int(payload.get("creative_plan_revision") or 0),
        "node_id": str(payload.get("creative_plan_node_id") or ""),
        "node_kind": str(payload.get("creative_plan_node_kind") or ""),
        "binding_status": str(payload.get("creative_plan_binding_status") or ""),
        "scene_policy": (
            dict(payload["creative_scene_policy"])
            if isinstance(payload.get("creative_scene_policy"), dict)
            else {}
        ),
        "required_gates": _strings(payload.get("creative_plan_required_gates")),
    }


def _strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]
