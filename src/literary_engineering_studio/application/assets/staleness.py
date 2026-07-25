"""Project Engine-backed stale evidence for owner asset mutations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.context_broker import context_trace_status


_DOWNSTREAM_STAGES = (
    "context",
    "roleplay",
    "branch",
    "composition",
    "candidate",
    "review",
    "promotion",
)


def build_formal_stale_propagation(
    project_root: Path,
    changed_relative_path: str,
) -> dict[str, object]:
    """Prove which formal scene chains became stale after an asset write."""

    root = project_root.resolve()
    relative = changed_relative_path.replace("\\", "/").lstrip("./")
    entries: list[dict[str, str]] = []
    trace_root = root / "memory" / "context_packets"
    if trace_root.is_dir():
        for trace_path in sorted(trace_root.glob("*.trace.json")):
            payload = _read_json(trace_path)
            if not _trace_loaded_path(payload, relative):
                continue
            scene_id = str(payload.get("scene_id") or trace_path.name.removesuffix(".trace.json"))
            context_path = trace_path.with_name(f"{scene_id}.md")
            state = context_trace_status(root, scene_id, context_path)
            entries.append(
                {
                    "scene_id": scene_id,
                    "context_trace": trace_path.relative_to(root).as_posix(),
                    "status": state.status,
                    "reason": state.message,
                }
            )
    scene_ids = sorted({entry["scene_id"] for entry in entries})
    propagated = bool(entries) and all(entry["status"] == "stale" for entry in entries)
    return {
        "schema": "arcvellum/archive-stale-propagation/v1",
        "status": "propagated" if propagated else "not-required" if not entries else "incomplete",
        "mechanism": "engine-context-trace-sha256",
        "changed_path": relative,
        "scene_ids": scene_ids,
        "entries": entries,
        "invalidated_stages": list(_DOWNSTREAM_STAGES) if entries else [],
        "historical_prose": "preserved",
    }


def build_formal_stale_preview(
    project_root: Path,
    changed_relative_paths: tuple[str, ...],
) -> dict[str, object]:
    """Project affected formal scene chains without mutating project truth."""

    root = project_root.resolve()
    relatives = {
        value.replace("\\", "/").lstrip("./")
        for value in changed_relative_paths
        if value.strip()
    }
    entries: list[dict[str, object]] = []
    trace_root = root / "memory" / "context_packets"
    if trace_root.is_dir() and relatives:
        for trace_path in sorted(trace_root.glob("*.trace.json")):
            payload = _read_json(trace_path)
            matched = sorted(relative for relative in relatives if _trace_loaded_path(payload, relative))
            if not matched:
                continue
            scene_id = str(payload.get("scene_id") or trace_path.name.removesuffix(".trace.json"))
            entries.append(
                {
                    "scene_id": scene_id,
                    "context_trace": trace_path.relative_to(root).as_posix(),
                    "changed_paths": matched,
                }
            )
    return {
        "schema": "arcvellum/archive-stale-preview/v1",
        "status": "would-propagate" if entries else "not-required",
        "mechanism": "engine-context-trace-sha256",
        "scene_ids": sorted({str(entry["scene_id"]) for entry in entries}),
        "entries": entries,
        "invalidated_stages": list(_DOWNSTREAM_STAGES) if entries else [],
        "historical_prose": "preserved",
    }


def _trace_loaded_path(payload: dict[str, Any], relative: str) -> bool:
    sources = payload.get("loaded_sources")
    if not isinstance(sources, list):
        return False
    return any(
        isinstance(source, dict)
        and str(source.get("relative_path") or "").replace("\\", "/").lstrip("./") == relative
        for source in sources
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
