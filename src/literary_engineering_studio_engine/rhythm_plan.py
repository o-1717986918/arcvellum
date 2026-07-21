"""User-managed, versioned narrative rhythm targets."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .narrative_rhythm import analyze_narrative_rhythm_sequence, narrative_rhythm_contract, normalize_tension_curve


RHYTHM_PLAN_SCHEMA = "literary-engineering-workbench/rhythm-plan/v0.1"
PACE_VALUES = {"slow", "slow_to_fast", "balanced", "fast_to_slow", "fast"}
ROLE_VALUES = {"setup", "transition", "information", "emotion", "conflict", "action", "turn", "aftermath", "mixed"}


def rhythm_plan_path(root: Path) -> Path:
    return root.resolve() / "plot" / "rhythm_plan.json"


def load_rhythm_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    stored = _read_json(rhythm_plan_path(root))
    stored_scenes = stored.get("scenes") if isinstance(stored.get("scenes"), dict) else {}
    entries: list[dict[str, Any]] = []
    for path in sorted((root / "scenes").glob("*.yaml")) if (root / "scenes").is_dir() else []:
        if path.name.startswith("_"):
            continue
        scene_id = _scalar(path.read_text(encoding="utf-8", errors="ignore"), "scene_id") or path.stem
        chapter_id = _scalar(path.read_text(encoding="utf-8", errors="ignore"), "chapter_id") or "unassigned"
        contract = narrative_rhythm_contract(root, path)
        rhythm = contract.get("narrative_rhythm") if isinstance(contract.get("narrative_rhythm"), dict) else {}
        curve = normalize_tension_curve(rhythm.get("tension_curve")) or {"entry": 2, "peak": 3, "exit": 2}
        entries.append({
            "scene_id": scene_id,
            "chapter_id": chapter_id,
            "title": _scalar(path.read_text(encoding="utf-8", errors="ignore"), "title") or scene_id,
            "pace": str(rhythm.get("pace") or "balanced"),
            "rhythm_role": str(rhythm.get("rhythm_role") or "mixed"),
            "scene_function": _strings(rhythm.get("scene_function")),
            "tension_curve": curve,
            "source": "rhythm-plan" if scene_id in stored_scenes else str(contract.get("source") or "default"),
        })
    chapters: dict[str, dict[str, Any]] = {}
    for chapter_id in sorted({str(entry["chapter_id"]) for entry in entries}):
        chapter_entries = [entry for entry in entries if entry["chapter_id"] == chapter_id]
        chapters[chapter_id] = analyze_narrative_rhythm_sequence(chapter_entries)
    return {
        "schema": RHYTHM_PLAN_SCHEMA,
        "revision": int(stored.get("revision") or 0),
        "digest": str(stored.get("digest") or ""),
        "updated_at": str(stored.get("updated_at") or ""),
        "entries": entries,
        "chapters": chapters,
        "stored": bool(stored),
    }


def save_rhythm_plan(root: Path, entries: list[dict[str, Any]], updated_by: str = "studio-user") -> dict[str, Any]:
    root = root.resolve()
    known = {_scalar(path.read_text(encoding="utf-8", errors="ignore"), "scene_id") or path.stem for path in (root / "scenes").glob("*.yaml")}
    normalized: dict[str, dict[str, Any]] = {}
    for entry in entries:
        scene_id = str(entry.get("scene_id") or "").strip()
        if not scene_id or scene_id not in known:
            raise ValueError(f"unknown rhythm-plan scene: {scene_id or 'missing'}")
        pace = str(entry.get("pace") or "balanced").strip().lower()
        role = str(entry.get("rhythm_role") or "mixed").strip().lower()
        curve = normalize_tension_curve(entry.get("tension_curve"))
        if pace not in PACE_VALUES:
            raise ValueError(f"unsupported scene pace: {pace}")
        if role not in ROLE_VALUES:
            raise ValueError(f"unsupported rhythm role: {role}")
        if curve is None:
            raise ValueError(f"scene {scene_id} requires entry/peak/exit tension values from 1 to 5")
        normalized[scene_id] = {
            "pace": pace,
            "rhythm_role": role,
            "scene_function": _strings(entry.get("scene_function")),
            "tension_curve": curve,
        }
    previous = _read_json(rhythm_plan_path(root))
    digest = hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    previous_digest = str(previous.get("digest") or "")
    revision = int(previous.get("revision") or 0) + (1 if digest != previous_digest else 0)
    payload = {
        "schema": RHYTHM_PLAN_SCHEMA,
        "revision": revision,
        "digest": digest,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": updated_by,
        "scenes": normalized,
    }
    _write_json_atomic(rhythm_plan_path(root), payload)
    return load_rhythm_plan(root)


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _scalar(text: str, key: str) -> str:
    import re
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    return match.group(1).strip().strip("\"'") if match else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
