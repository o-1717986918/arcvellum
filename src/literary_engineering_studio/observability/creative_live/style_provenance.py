"""Read-only prose-style provenance for Creative Live."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def latest_style_provenance(project_root: str | Path, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    event = next((item for item in reversed(events) if item.get("event") == "style.projection.selected"), None)
    if event is not None:
        return _from_event(event)
    candidates = Path(project_root).resolve() / "drafts" / "candidates"
    if not candidates.is_dir():
        return None
    paths = sorted(candidates.glob("*.prompt.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths[:12]:
        payload = _read_prompt_manifest(path)
        if payload is not None:
            return _from_manifest(payload)
    return None


def _from_event(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    return {
        "source": "lean-runtime",
        "scene_id": str(data.get("scene_id") or ""),
        "style_version_id": str(data.get("style_version_id") or ""),
        "selection_status": str(data.get("selection_status") or ""),
        "selector_version": str(data.get("selector_version") or ""),
        "selection_digest": str(data.get("selection_digest") or ""),
        "reference_ids": _strings(data.get("reference_ids")),
        "technique_axes": _strings(data.get("technique_axes")),
        "expression_plan_digest": str(data.get("expression_plan_digest") or ""),
        "voice_digest": str(data.get("voice_digest") or ""),
    }


def _read_prompt_manifest(path: Path) -> dict[str, Any] | None:
    if path.stat().st_size > 2_000_000:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("style_reference_selection"), dict) else None


def _from_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    selection = payload["style_reference_selection"]
    references = _references(selection)
    mount = payload.get("style_mount_snapshot") if isinstance(payload.get("style_mount_snapshot"), dict) else {}
    return {
        "source": "formal-manifest",
        "scene_id": Path(str(payload.get("scene") or "")).stem,
        "style_version_id": str(mount.get("version_id") or ""),
        "selection_status": str(selection.get("status") or ""),
        "selector_version": str(selection.get("selector_version") or ""),
        "selection_digest": str(selection.get("digest") or ""),
        "reference_ids": [str(item.get("unit_id") or "") for item in references if isinstance(item, dict)],
        "technique_axes": [str(axis) for item in references if isinstance(item, dict) for axis in _strings(item.get("technique_axes"))],
        "expression_plan_digest": str(payload.get("expression_plan_digest") or ""),
        "voice_digest": str(payload.get("voice_digest") or ""),
    }


def _strings(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _references(selection: dict[str, Any]) -> list[dict[str, Any]]:
    value = selection.get("references")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


__all__ = ["latest_style_provenance"]
