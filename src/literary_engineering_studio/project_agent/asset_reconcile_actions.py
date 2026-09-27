"""Project Agent access to the existing lean planning-asset route."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .action_receipts import action_receipt


def asset_reconcile_action(
    reconcile_assets: Callable[..., Mapping[str, Any]],
    invalidate_project: Callable[[Path, str], Any] | None = None,
):
    def action(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        asset_id = str(arguments.get("asset_id") or "").strip()
        reason = str(arguments.get("reason") or "").strip()
        if not asset_id:
            raise ValueError("project_assets_reconcile requires a planned asset_id")
        if len(reason) < 6:
            raise ValueError("project_assets_reconcile requires an explanatory reason")
        result = dict(reconcile_assets(root, target_asset_id=asset_id))
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-assets-reconcile")
        payload = {"ok": True, "operation": "assets_reconcile", "asset_id": asset_id,
                   "reason": reason, **result}
        return {**payload, "receipt": action_receipt("assets_reconcile", payload)}

    return action


__all__ = ["asset_reconcile_action"]
