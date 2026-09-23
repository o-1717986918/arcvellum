"""Read recent completed lean-scene style selections without loading prose."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def recent_lean_reference_ids(data_root: Path, scene_id: str, mount: dict[str, str]) -> tuple[str, ...]:
    directory = data_root / "scene-transactions"
    if not directory.is_dir():
        return ()
    paths = sorted(directory.glob("*/style_selection.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    recent: list[str] = []
    seen = {scene_id}
    for path in paths[:40]:
        if not next(path.parent.glob("creative_result_*.json"), None):
            continue
        saved = _read_selection(path)
        previous_scene = str(saved.get("scene_id") or "")
        if not previous_scene or previous_scene in seen or saved.get("style_mount_snapshot") != mount:
            continue
        seen.add(previous_scene)
        selection = saved.get("selection") or {}
        recent.extend(str(row["unit_id"]) for row in selection.get("references", []) if row.get("unit_id"))
        if len(seen) >= 5:
            break
    return tuple(recent)


def scene_reference_context(project_root: Path, scene_id: str, brief: dict[str, Any]) -> str:
    """Use scene-specific prose facts, excluding repeated template and rhythm boilerplate."""

    brief_cues = {
        key: brief.get(key)
        for key in ("scene_id", "objective", "location", "participants", "viewpoint", "scene_function", "external_conflict", "internal_conflict")
        if brief.get(key)
    }
    path = project_root / "scenes" / f"{scene_id}.yaml"
    if not path.is_file():
        return json.dumps(brief_cues, ensure_ascii=False, sort_keys=True)
    try:
        scene = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, YAMLError):
        scene = {}
    if not isinstance(scene, dict):
        scene = {}
    conflict = scene.get("conflict") if isinstance(scene.get("conflict"), dict) else {}
    experience = scene.get("reader_experience") if isinstance(scene.get("reader_experience"), dict) else {}
    rhythm = scene.get("narrative_rhythm") if isinstance(scene.get("narrative_rhythm"), dict) else {}
    cues = {
        "title": scene.get("title"), "scene_goal": scene.get("scene_goal"),
        "location": scene.get("location"), "conflict": conflict,
        "actions": scene.get("actions"), "revealed_info": scene.get("revealed_info"),
        "tension_source": experience.get("tension_source"),
        "scene_function": rhythm.get("scene_function"),
    }
    return json.dumps({"brief": brief_cues, "scene_cues": cues}, ensure_ascii=False, sort_keys=True)


def _read_selection(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def projection_digest(selection: dict[str, Any], expression: dict[str, Any]) -> str:
    selection_digest = str(selection.get("digest") or hashlib.sha256(
        json.dumps(selection, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest())[:16]
    encoded = json.dumps(
        {"selection": selection_digest, "expression": expression},
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


__all__ = ["recent_lean_reference_ids", "projection_digest"]
