"""User-facing recycle-bin projection without internal storage paths."""

from __future__ import annotations

from typing import Any


def project_recycle_bin(payload: dict[str, object]) -> dict[str, object]:
    raw_items = payload.get("items")
    items = [_project_item(item) for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
    active = sum(1 for item in items if item["status"] == "active")
    restored = sum(1 for item in items if item["status"] == "restored")
    return {
        "schema": "arcvellum/archive-recycle-bin-view/v1",
        "summary": {
            "total": len(items),
            "active": active,
            "restored": restored,
        },
        "items": items,
        "synchronization": payload.get("synchronization") if isinstance(payload.get("synchronization"), dict) else {},
    }


def _project_item(item: dict[str, Any]) -> dict[str, object]:
    status = str(item.get("status") or "")
    return {
        "entry_id": str(item.get("entry_id") or ""),
        "asset_id": str(item.get("asset_id") or ""),
        "asset_type": str(item.get("asset_type") or ""),
        "revision": str(item.get("revision") or ""),
        "title": str(item.get("title") or item.get("asset_id") or ""),
        "media_type": str(item.get("media_type") or "text/plain"),
        "status": status,
        "status_label": "待恢复" if status == "active" else "已恢复",
        "original_path": str(item.get("original_path") or ""),
        "reason": str(item.get("reason") or ""),
        "archived_at": str(item.get("archived_at") or ""),
        "restored_at": str(item.get("restored_at") or ""),
    }
