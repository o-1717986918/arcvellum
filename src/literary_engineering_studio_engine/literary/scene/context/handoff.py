"""Formal scene-to-scene continuity handoffs.

The writing route may not rely on an Agent remembering an earlier draft.  A
handoff is a compact, digest-bound summary of the *promoted* prior scene and
of any State/Canon applies that followed it.  It is deliberately data-first:
the platform Agent supplies the editorial interpretation in the approved
patches, while this module gives the next task one stable location to verify.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....atomic_io import atomic_write_text


HANDOFF_SCHEMA = "literary-engineering-workbench/scene-handoff/v1"


def handoff_path(root: Path, scene_id: str) -> Path:
    return root.resolve() / "workflow" / "handoffs" / f"{scene_id}.json"


def ordered_scene_ids(root: Path) -> list[str]:
    """Return formal scenes in authored timeline order without guessing prose."""

    rows: list[tuple[int, str]] = []
    for path in sorted((root.resolve() / "scenes").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        scene_id = _scalar(text, "scene_id") or path.stem
        timeline = _integer(_scalar(text, "timeline_order"))
        rows.append((timeline if timeline is not None else 10**9, scene_id))
    return [scene_id for _timeline, scene_id in sorted(rows, key=lambda row: (row[0], row[1]))]


def previous_scene_id(root: Path, scene_id: str) -> str:
    ids = ordered_scene_ids(root)
    try:
        index = ids.index(scene_id)
    except ValueError:
        return ""
    return ids[index - 1] if index > 0 else ""


def build_scene_handoff(project_root: Path, scene_id: str) -> Path:
    """Materialize the post-scene continuity record after formal promotion.

    The deterministic record refuses to invent events: draft excerpts and
    approved apply manifests are only supplied as evidence.  A pending
    ``agent_summary`` remains explicit until the state/canon tasks have
    supplied an approved interpretation.
    """

    root = project_root.resolve()
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    promotion = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    if not draft.is_file() or not promotion.is_file():
        raise FileNotFoundError(f"scene handoff requires promoted draft and promotion manifest for {scene_id}")

    draft_sha = _sha256(draft)
    state_apply = _read_json(root / "characters" / "state_patches" / f"{scene_id}_state_apply.json")
    canon_apply = _read_json(root / "canon" / "patches" / f"{scene_id}_canon_apply.json")
    scene_text = _read(root / "scenes" / f"{scene_id}.yaml")
    payload = {
        "schema": HANDOFF_SCHEMA,
        "scene_id": scene_id,
        "previous_scene_id": previous_scene_id(root, scene_id),
        "promoted_draft": f"drafts/scenes/{scene_id}.md",
        "promoted_draft_sha256": draft_sha,
        "promotion_manifest": f"drafts/promotions/{scene_id}_promotion.json",
        "time_after": _scalar(scene_text, "story_time") or _scalar(scene_text, "time_after"),
        "location_after": _scalar(scene_text, "location") or _scalar(scene_text, "location_after"),
        "character_state_deltas": _state_deltas(state_apply),
        "relationship_debts": [],
        "unresolved_actions": [],
        "objects_in_motion": [],
        "information_distribution": [],
        "outgoing_hooks": _scene_hooks(scene_text),
        "approved_state_apply": _apply_ref(state_apply, root),
        "approved_canon_apply": _apply_ref(canon_apply, root),
        "emotional_aftertaste": "",
        "agent_summary": {
            "status": "pending" if not (state_apply or canon_apply) else "partial",
            "note": "Complete the approved state/canon task before treating this handoff as a fully interpreted continuity record.",
        },
        "evidence_paths": [
            f"drafts/scenes/{scene_id}.md",
            f"drafts/promotions/{scene_id}_promotion.json",
            *([f"characters/state_patches/{scene_id}_state_apply.json"] if state_apply else []),
            *([f"canon/patches/{scene_id}_canon_apply.json"] if canon_apply else []),
        ],
        "created_at": _now(),
    }
    target = handoff_path(root, scene_id)
    atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return target


def scene_handoff_status(root: Path, scene_id: str) -> tuple[bool, str, dict[str, Any]]:
    """Validate the formal predecessor handoff needed by ``scene_id``.

    Legacy/new projects without a promoted predecessor remain migratable. Once
    a predecessor is promoted, a missing or stale handoff becomes a hard
    blocker rather than silently falling back to the Agent's chat memory.
    """

    root = root.resolve()
    previous = previous_scene_id(root, scene_id)
    if not previous:
        return True, "first scene does not require a predecessor handoff", {}
    previous_draft = root / "drafts" / "scenes" / f"{previous}.md"
    if not previous_draft.is_file():
        return True, "predecessor has not been promoted; handoff deferred for migration", {}
    path = handoff_path(root, previous)
    if not path.is_file():
        return False, f"missing required predecessor handoff: {path.relative_to(root).as_posix()}", {}
    payload = _read_json(path)
    if payload.get("schema") != HANDOFF_SCHEMA or str(payload.get("scene_id") or "") != previous:
        return False, f"invalid predecessor handoff: {path.relative_to(root).as_posix()}", payload
    actual = _sha256(previous_draft)
    if str(payload.get("promoted_draft_sha256") or "") != actual:
        return False, f"predecessor handoff is stale for {previous}", payload
    return True, f"predecessor handoff verified: {path.relative_to(root).as_posix()}", payload


def _state_deltas(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("applied_characters") if isinstance(payload.get("applied_characters"), list) else []
    return [
        {
            "character_id": str(row.get("character_id") or ""),
            "file": str(row.get("file") or ""),
            "updates": int(row.get("updates") or 0),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _apply_ref(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    if not payload:
        return {"status": "not_applied"}
    return {
        "status": str(payload.get("status") or "applied"),
        "applied_at": str(payload.get("applied_at") or ""),
        "manifest_sha256": _sha256_from_payload(payload),
    }


def _scene_hooks(text: str) -> list[Any]:
    # The detailed bridge remains an Agent-owned composition field.  This
    # deterministic fallback keeps explicit authored hooks available.
    return _list_value(text, "outgoing_hooks")


def _list_value(text: str, key: str) -> list[str]:
    inline = re.search(rf"(?m)^\s*{re.escape(key)}:\s*\[(.*?)\]\s*$", text)
    if inline:
        return [item.strip().strip("'\"") for item in inline.group(1).split(",") if item.strip()]
    values: list[str] = []
    in_block = False
    indent = 0
    for line in text.splitlines():
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            in_block = True
            indent = len(line) - len(line.lstrip())
            continue
        if not in_block:
            continue
        stripped = line.strip()
        current = len(line) - len(line.lstrip())
        if stripped and current <= indent and not stripped.startswith("-"):
            break
        if stripped.startswith("-"):
            values.append(stripped[1:].strip().strip("'\""))
    return [item for item in values if item]


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*['\"]?([^'\"\n#]+)", text)
    return match.group(1).strip().strip("'\"") if match else ""


def _integer(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_from_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
