"""Project Agent adapter for a versioned scene creator persona."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def creator_persona_update_action(save: Callable[..., dict[str, Any]]):
    def update(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        text = str(arguments.get("persona_text") or "").strip()
        reason = str(arguments.get("reason") or "").strip()
        saved = save(root, text, reason=reason)
        return {"ok": True, "operation": "update_creator_persona", "persona": saved,
                "effect": "future-scene-transactions",
                "receipt": action_receipt("update_creator_persona", saved)}
    return update


__all__ = ["creator_persona_update_action"]
