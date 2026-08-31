"""Present review and validation evidence as a dedicated literary timeline."""

from __future__ import annotations

from typing import Any


def review_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": item.get("event_id"),
            "event": item.get("event"),
            "at": item.get("at"),
            "task_id": item.get("task_id"),
            "route": item.get("route"),
            "title": (item.get("data") or {}).get("title"),
            "message": (item.get("data") or {}).get("message"),
            "passed": _passed(item),
            "status": (item.get("data") or {}).get("status"),
            "findings": (item.get("data") or {}).get("findings") or [],
            "artifact_id": (item.get("artifact") or {}).get("artifact_id"),
        }
        for item in events
        if item.get("channel") == "review"
    ][-80:]


def _passed(item: dict[str, Any]) -> bool | None:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    if isinstance(data.get("passed"), bool):
        return data["passed"]
    event = str(item.get("event") or "")
    if event.endswith(("passed", "completed")):
        return True
    if event.endswith(("failed", "rejected")):
        return False
    return None


__all__ = ["review_events"]
