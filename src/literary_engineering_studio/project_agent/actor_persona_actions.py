"""Project Agent adapter for editable actor initialization tags."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def actor_persona_update_action(
    save: Callable[..., dict[str, Any]],
    invalidate_project: Callable[[Path, str], Any] | None,
):
    def update(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        character_id = str(arguments.get("character_id") or "").strip()
        sections = arguments.get("sections")
        if not character_id or not isinstance(sections, dict):
            raise ValueError("project_actor_persona_update requires character_id and persona sections")
        saved = save(root, character_id, sections)
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-actor-persona")
        return {
            "ok": True,
            "operation": "update_actor_persona",
            "profile": saved,
            "effect": "future-scene-transactions",
            "receipt": action_receipt("update_actor_persona", saved),
        }

    return update


__all__ = ["actor_persona_update_action"]
