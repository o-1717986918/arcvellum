"""Read-only creation strategy projection for the AO-8 product surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from literary_engineering_studio.orchestration import OrchestrationSettings

STRATEGY_PROJECTION_SCHEMA = "arcvellum/strategy-projection/v1"


def strategy_projection(
    root: Path,
    settings: OrchestrationSettings,
) -> dict[str, Any]:
    """Project orchestration settings and the active plan for display."""
    root = root.resolve()
    return {
        "schema": STRATEGY_PROJECTION_SCHEMA,
        "settings": {
            "enabled": settings.enabled,
            "mode": settings.effective_mode.value,
            "preset": settings.strategy_preset.value,
        },
        "active_plan": _active_plan_summary(root),
        "rolling_horizon": None,
    }


def typed_plan_events(
    root: Path,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return a safe, ordered subset of typed plan events from run audits."""
    root = root.resolve()
    limit = max(1, min(200, int(limit or 50)))
    runs = root / "workflow" / "orchestration" / "runs"
    if not runs.is_dir():
        return []
    parsed: list[dict[str, Any]] = []
    for path in sorted(runs.glob("*/events.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            item = _parse_event_line(line)
            if item is not None:
                parsed.append(item)
    parsed.sort(key=lambda item: str(item.get("created_at") or ""))
    return parsed[-limit:]


def _active_plan_summary(root: Path) -> dict[str, Any] | None:
    path = root / "workflow" / "orchestration" / "active_plan.json"
    if not path.is_file():
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        scope = {}
    return {
        "plan_id": str(payload.get("plan_id") or ""),
        "revision": int(payload.get("revision") or 0),
        "status": str(payload.get("status") or "unknown"),
        "scope_kind": str(scope.get("kind") or ""),
        "scope_key": str(scope.get("key") or ""),
    }


def _parse_event_line(line: str) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        import json

        payload = json.loads(line)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    event_id = str(payload.get("event_id") or "")
    return {
        "event_id": event_id,
        "event_type": str(payload.get("type") or payload.get("event_type") or ""),
        "plan_id": str(payload.get("plan_id") or ""),
        "revision": payload.get("revision"),
        "created_at": str(payload.get("created_at") or ""),
        "scope_key": str(payload.get("scope_key") or ""),
    }
