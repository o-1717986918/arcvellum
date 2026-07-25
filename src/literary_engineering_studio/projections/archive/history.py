"""Safe user-facing Archive revision history projection."""

from __future__ import annotations

from pathlib import Path

from ...application.assets.loader import AssetLoader
from ...application.assets.revisions import AssetRevisionService


def project_asset_history(
    project_root: Path,
    asset_id: str,
    loader: AssetLoader,
    revisions: AssetRevisionService,
) -> dict[str, object]:
    current = loader.load(project_root, asset_id)
    history = revisions.history(project_root, asset_id)
    transactions = [
        {
            "transaction_id": item["transaction_id"],
            "base_revision": item["base_revision"],
            "new_revision": item["new_revision"],
            "operation": item.get("operation", "replace"),
            "authority": item["authority"],
            "semantic_review": item["semantic_review"],
            "reason": item["reason"],
            "impact": item["impact"],
            "stale_propagation": item["stale_propagation"],
            "created_at": item["created_at"],
        }
        for item in history["transactions"]
    ]
    revision_rows = [
        {
            "revision": item["revision"],
            "transaction_id": item["transaction_id"],
            "snapshot_role": item["snapshot_role"],
            "created_at": item["created_at"],
            "current": item["revision"] == current.revision,
        }
        for item in history["revisions"]
    ]
    return {
        "schema": "arcvellum/archive-history/v1",
        "asset_id": asset_id,
        "current_revision": current.revision,
        "transactions": transactions,
        "revisions": revision_rows,
        "synchronization": history["synchronization"],
    }
