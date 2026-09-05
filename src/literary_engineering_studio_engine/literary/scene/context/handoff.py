"""Digest-bound scene-to-scene continuity handoffs.

The State, Canon, and continuity routes already contain the Agent's reviewed
literary judgments. A handoff therefore remains deterministic: it composes
those accepted artifacts into one compact contract and refuses to run while
any upstream writeback is pending or stale.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ....atomic_io import atomic_write_text
from ...assets.canon.evolver import canon_writeback_status
from ...assets.canon.paths import canon_apply_manifest_for_scene, canon_patch_path
from ...assets.continuity.ledger import continuity_ledger_status, continuity_ledger_task_status, delta_path
from ..facts import load_scene_facts
from ..state.apply import state_patch_writeback_status


HANDOFF_SCHEMA = "literary-engineering-workbench/scene-handoff/v2"
_YAML = YAML(typ="safe")


def handoff_path(root: Path, scene_id: str) -> Path:
    return root.resolve() / "workflow" / "handoffs" / f"{scene_id}.json"


def ordered_scene_ids(root: Path) -> list[str]:
    """Return formal scenes in authored timeline order."""

    rows: list[tuple[int, str]] = []
    for path in sorted((root.resolve() / "scenes").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        payload = _read_yaml(path)
        scene_id = _text(payload.get("scene_id")) or path.stem
        timeline = _timeline_order(payload)
        rows.append((timeline if timeline is not None else 10**9, scene_id))
    return [scene_id for _timeline, scene_id in sorted(rows, key=lambda row: (row[0], row[1]))]


def previous_scene_id(root: Path, scene_id: str) -> str:
    ids = ordered_scene_ids(root)
    try:
        index = ids.index(scene_id)
    except ValueError:
        return ""
    return ids[index - 1] if index > 0 else ""


def next_scene_id(root: Path, scene_id: str) -> str:
    ids = ordered_scene_ids(root)
    try:
        index = ids.index(scene_id)
    except ValueError:
        return ""
    return ids[index + 1] if index + 1 < len(ids) else ""


def build_scene_handoff(project_root: Path, scene_id: str) -> Path:
    """Compose reviewed post-scene evidence into the formal handoff."""

    root = project_root.resolve()
    errors = scene_handoff_source_errors(root, scene_id)
    if errors:
        raise ValueError("scene handoff is not ready: " + "; ".join(errors))
    payload = _handoff_payload(root, scene_id, _handoff_artifacts(root, scene_id))
    target = handoff_path(root, scene_id)
    atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return target


def _handoff_payload(
    root: Path, scene_id: str, artifacts: dict[str, Path]
) -> dict[str, Any]:
    facts = load_scene_facts(artifacts["scene"])
    scene_payload = _read_yaml(artifacts["scene"])
    state_payload = _read_json(artifacts["state_patch"])
    state_apply_payload = _read_json(artifacts["state_apply"])
    canon_status = canon_writeback_status(root, scene_id)
    continuity_payload = _read_json(artifacts["continuity_delta"])
    evidence = {
        "promoted_draft": _evidence(root, artifacts["draft"], "applied"),
        "promotion_manifest": _evidence(root, artifacts["promotion"], "applied"),
        "state_patch": _evidence(root, artifacts["state_patch"], str(state_patch_writeback_status(root, scene_id).get("status") or "")),
        "state_apply": _evidence(root, artifacts["state_apply"], _optional_status(state_apply_payload, "not_required")),
        "canon_patch": _evidence(root, artifacts["canon_patch"], str(canon_status.get("status") or "")),
        "canon_apply": _evidence(root, artifacts["canon_apply"], _optional_status(_read_json(artifacts["canon_apply"]), "not_required")),
        "continuity_delta": _evidence(root, artifacts["continuity_delta"], "reviewed"),
        "continuity_review": _evidence(root, artifacts["continuity_review"], "pass"),
        "continuity_apply": _evidence(root, artifacts["continuity_apply"], "applied"),
    }
    relationship_debts = _relationship_debts(state_payload)
    unresolved_actions = _unresolved_actions(state_payload)
    information_distribution = _information_distribution(continuity_payload)
    outgoing_hooks = list(facts.next_hooks)
    emotional_aftertaste = _emotional_aftertaste(scene_payload)
    return {
        "schema": HANDOFF_SCHEMA,
        "scene_id": scene_id,
        "source_scene_id": scene_id,
        "successor_scene_id": next_scene_id(root, scene_id),
        "previous_scene_id": previous_scene_id(root, scene_id),
        "promoted_draft": _rel(artifacts["draft"], root),
        "promoted_draft_sha256": _sha256(artifacts["draft"]),
        "promotion_manifest": _rel(artifacts["promotion"], root),
        "evidence": evidence,
        "time_after": _story_time(scene_payload),
        "location_after": facts.location or _text(scene_payload.get("location_after")),
        "character_state_deltas": _state_deltas(state_payload, state_apply_payload),
        "relationship_debts": relationship_debts,
        "unresolved_actions": unresolved_actions,
        "objects_in_motion": [],
        "information_distribution": information_distribution,
        "outgoing_hooks": outgoing_hooks,
        "emotional_aftertaste": emotional_aftertaste,
        "causal_pressure_for_next_scene": "；".join(outgoing_hooks),
        "semantic_coverage": {
            "relationship_debts": _coverage(relationship_debts, "reviewed state patch contains no relationship change"),
            "unresolved_actions": _coverage(unresolved_actions, "reviewed state patch contains no unresolved action"),
            "objects_in_motion": _coverage([], "no structured object-motion contract is declared for this scene"),
            "information_distribution": _coverage(information_distribution, "reviewed continuity delta contains no question or promise change"),
            "emotional_aftertaste": _coverage(emotional_aftertaste, "scene contract declares no explicit emotional aftertaste"),
        },
        "approved_state_apply": _apply_ref(state_apply_payload, artifacts["state_apply"], root),
        "approved_canon_apply": _apply_ref(_read_json(artifacts["canon_apply"]), artifacts["canon_apply"], root),
        "agent_summary": {
            "status": "complete",
            "note": "Deterministically composed from reviewed State, Canon, and continuity artifacts.",
        },
        "evidence_paths": [item["path"] for item in evidence.values() if item.get("path")],
        "source_digest": _evidence_digest(evidence),
        "status": "complete",
        "created_at": _now(),
    }


def _handoff_artifacts(root: Path, scene_id: str) -> dict[str, Path]:
    return {
        "scene": root / "scenes" / f"{scene_id}.yaml",
        "draft": root / "drafts" / "scenes" / f"{scene_id}.md",
        "promotion": root / "drafts" / "promotions" / f"{scene_id}_promotion.json",
        "state_patch": root / "characters" / "state_patches" / f"{scene_id}_state_patch.json",
        "state_apply": root / "characters" / "state_patches" / f"{scene_id}_state_apply.json",
        "canon_patch": canon_patch_path(root, scene_id),
        "canon_apply": canon_apply_manifest_for_scene(root, scene_id),
        "continuity_delta": delta_path(root, scene_id),
        "continuity_review": root / "reviews" / "continuity" / f"{scene_id}_ledger_review.json",
        "continuity_apply": root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json",
    }


def scene_handoff_source_errors(root: Path, scene_id: str) -> list[str]:
    """Return exact upstream reasons why ``scene_id`` cannot emit a handoff."""

    root = root.resolve()
    artifacts = _handoff_artifacts(root, scene_id)
    errors = _promotion_source_errors(artifacts["draft"], artifacts["promotion"], scene_id)
    if len(errors) == 1 and errors[0].startswith("promoted draft"):
        return errors
    errors.extend(_writeback_source_errors(root, scene_id))
    errors.extend(_continuity_source_errors(root, scene_id, artifacts))
    return errors


def _promotion_source_errors(draft: Path, promotion: Path, scene_id: str) -> list[str]:
    if not draft.is_file() or not promotion.is_file():
        return [f"promoted draft and promotion manifest are required for {scene_id}"]
    promoted = _read_json(promotion)
    recorded_draft = str(promoted.get("draft_sha256") or "").lower()
    if not recorded_draft or recorded_draft != _sha256(draft):
        return ["promotion manifest does not bind the current promoted draft"]
    return []


def _writeback_source_errors(root: Path, scene_id: str) -> list[str]:
    errors: list[str] = []
    state_status = state_patch_writeback_status(root, scene_id)
    if str(state_status.get("status") or "") not in {"pass", "not_required", "rejected"}:
        errors.append(f"state writeback is incomplete: {state_status.get('message')}")
    canon_status = canon_writeback_status(root, scene_id)
    if str(canon_status.get("status") or "") not in {"pass", "not_required"}:
        errors.append(f"canon writeback is incomplete: {canon_status.get('message')}")
    return errors


def _continuity_source_errors(
    root: Path, scene_id: str, artifacts: dict[str, Path]
) -> list[str]:
    errors: list[str] = []
    continuity_ok, continuity_message, _payload = continuity_ledger_status(root, scene_id, require_review=True)
    if not continuity_ok:
        errors.append(continuity_message)
    for review in (False, True):
        task_ok, task_message = continuity_ledger_task_status(root, scene_id, review=review)
        if not task_ok:
            errors.append(task_message)
    apply_payload = _read_json(artifacts["continuity_apply"])
    delta = artifacts["continuity_delta"]
    if (
        str(apply_payload.get("status") or "") != "applied"
        or not delta.is_file()
        or str(apply_payload.get("delta_sha256") or "").lower() != _sha256(delta)
    ):
        errors.append("continuity ledger apply receipt is missing or stale")
    return errors


def scene_handoff_source_status(root: Path, scene_id: str) -> tuple[bool, str, dict[str, Any]]:
    """Validate the handoff emitted by one completed scene."""

    root = root.resolve()
    errors = scene_handoff_source_errors(root, scene_id)
    path = handoff_path(root, scene_id)
    if errors:
        return False, "; ".join(errors), _read_json(path)
    if not path.is_file():
        return False, f"missing scene handoff: {_rel(path, root)}", {}
    payload = _read_json(path)
    if payload.get("schema") != HANDOFF_SCHEMA or str(payload.get("source_scene_id") or "") != scene_id:
        return False, f"invalid scene handoff: {_rel(path, root)}", payload
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    evidence_errors = _evidence_errors(root, evidence)
    if evidence_errors:
        return False, "scene handoff evidence is stale: " + "; ".join(evidence_errors), payload
    if str(payload.get("source_digest") or "") != _evidence_digest(evidence):
        return False, "scene handoff source digest is stale", payload
    if str(payload.get("successor_scene_id") or "") != next_scene_id(root, scene_id):
        return False, "scene handoff successor binding is stale", payload
    return True, f"scene handoff verified: {_rel(path, root)}", payload


def scene_handoff_status(root: Path, scene_id: str) -> tuple[bool, str, dict[str, Any]]:
    """Validate the predecessor handoff required by ``scene_id``."""

    root = root.resolve()
    previous = previous_scene_id(root, scene_id)
    if not previous:
        return True, "first scene does not require a predecessor handoff", {}
    previous_draft = root / "drafts" / "scenes" / f"{previous}.md"
    if not previous_draft.is_file():
        return True, "predecessor has not been promoted; handoff deferred for migration", {}
    passed, message, payload = scene_handoff_source_status(root, previous)
    if passed and str(payload.get("successor_scene_id") or "") != scene_id:
        return False, f"predecessor handoff does not target {scene_id}", payload
    return passed, message.replace("scene handoff", "predecessor handoff"), payload


def _state_deltas(patch: dict[str, Any], applied: dict[str, Any]) -> list[dict[str, Any]]:
    applied_rows = applied.get("applied_characters") if isinstance(applied.get("applied_characters"), list) else []
    applied_by_id = {
        str(row.get("character_id") or ""): row
        for row in applied_rows
        if isinstance(row, dict)
    }
    rows: list[dict[str, Any]] = []
    for item in patch.get("characters") if isinstance(patch.get("characters"), list) else []:
        if not isinstance(item, dict):
            continue
        character_id = str(item.get("character_id") or "")
        applied_row = applied_by_id.get(character_id, {})
        rows.append(
            {
                "character_id": character_id,
                "file": str(item.get("file") or applied_row.get("file") or ""),
                "updates": int(applied_row.get("updates") or 0),
                "proposed_updates": item.get("proposed_updates") if isinstance(item.get("proposed_updates"), dict) else {},
            }
        )
    return rows


def _relationship_debts(patch: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in patch.get("characters") if isinstance(patch.get("characters"), list) else []:
        updates = item.get("proposed_updates") if isinstance(item, dict) and isinstance(item.get("proposed_updates"), dict) else {}
        relationships = updates.get("relationships") if isinstance(updates.get("relationships"), dict) else {}
        values.extend(_strings(relationships.get("candidate_changes")))
    source = patch.get("source_changes") if isinstance(patch.get("source_changes"), dict) else {}
    values.extend(_strings(source.get("relationship_changes")))
    return _unique(values)


def _unresolved_actions(patch: dict[str, Any]) -> list[dict[str, str]]:
    rows = patch.get("unresolved_changes") if isinstance(patch.get("unresolved_changes"), list) else []
    return [
        {"kind": str(item.get("kind") or "unresolved"), "text": str(item.get("text") or "")}
        for item in rows
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]


def _information_distribution(delta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, field in (("reader_question", "reader_question_changes"), ("promise", "promise_changes")):
        for item in delta.get(field) if isinstance(delta.get(field), list) else []:
            if isinstance(item, dict):
                rows.append({"kind": kind, **item})
    return rows


def _evidence(root: Path, path: Path, status: str) -> dict[str, str]:
    return {
        "path": _rel(path, root) if path.is_file() else "",
        "sha256": _sha256(path) if path.is_file() else "",
        "status": status,
    }


def _evidence_errors(root: Path, evidence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, value in evidence.items():
        if not isinstance(value, dict) or not value.get("path"):
            continue
        path = root / str(value["path"])
        if not path.is_file() or str(value.get("sha256") or "") != _sha256(path):
            errors.append(str(name))
    return errors


def _evidence_digest(evidence: dict[str, Any]) -> str:
    stable = {
        name: {"path": value.get("path", ""), "sha256": value.get("sha256", ""), "status": value.get("status", "")}
        for name, value in sorted(evidence.items())
        if isinstance(value, dict)
    }
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _apply_ref(payload: dict[str, Any], path: Path, root: Path) -> dict[str, str]:
    if not payload or not path.is_file():
        return {"status": "not_required", "path": "", "sha256": ""}
    return {
        "status": str(payload.get("status") or "applied"),
        "path": _rel(path, root),
        "sha256": _sha256(path),
        "applied_at": str(payload.get("applied_at") or ""),
    }


def _coverage(value: object, none_reason: str) -> dict[str, str]:
    present = bool(value)
    return {"status": "present" if present else "none", "none_reason": "" if present else none_reason}


def _story_time(payload: dict[str, Any]) -> str:
    direct = _text(payload.get("story_time") or payload.get("time_after"))
    if direct:
        return direct
    time_value = payload.get("time")
    if isinstance(time_value, dict):
        return _text(time_value.get("story_time") or time_value.get("label") or time_value.get("value"))
    return _text(time_value)


def _emotional_aftertaste(payload: dict[str, Any]) -> str:
    direct = _text(payload.get("emotional_aftertaste") or payload.get("reader_effect"))
    if direct:
        return direct
    rhythm = payload.get("narrative_rhythm")
    return _text(rhythm.get("reader_effect") or rhythm.get("exit_effect")) if isinstance(rhythm, dict) else ""


def _timeline_order(payload: dict[str, Any]) -> int | None:
    value: Any = payload.get("timeline_order")
    if value is None and isinstance(payload.get("time"), dict):
        value = payload["time"].get("timeline_order")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_status(payload: dict[str, Any], fallback: str) -> str:
    return str(payload.get("status") or fallback) if payload else fallback


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = _YAML.load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    return [str(item).strip() for item in rows if str(item).strip()]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _text(value: Any) -> str:
    return "" if value is None or isinstance(value, (dict, list)) else str(value).strip()


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "HANDOFF_SCHEMA",
    "build_scene_handoff",
    "handoff_path",
    "next_scene_id",
    "ordered_scene_ids",
    "previous_scene_id",
    "scene_handoff_source_errors",
    "scene_handoff_source_status",
    "scene_handoff_status",
]
