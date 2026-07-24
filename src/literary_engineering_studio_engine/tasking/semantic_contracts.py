"""Semantic evidence contracts for platform-agent workflow tasks.

Completion markers answer only whether an Agent declared a task finished.  The
formal writing route also needs a small, machine-checkable record of what the
Agent concluded so downstream commands can consume it instead of treating a
sidecar marker as creative evidence.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from ..agent_schema import validate_payload


SEMANTIC_ARTIFACTS: dict[str, dict[str, str]] = {
    "roleplay-agent-task": {
        "schema_name": "roleplay_result.v1",
        "kind": "roleplay-result",
        "filename": "roleplay_result.json",
        "consumed_by": "branch-manifest",
    },
    "composition-agent-task": {
        "schema_name": "composition_review.v1",
        "kind": "composition-review",
        "filename": "{scene_id}_composition_review.json",
        "consumed_by": "candidate-generation-provenance",
    },
    "state-agent-task": {
        "schema_name": "state_patch_review.v1",
        "kind": "state-patch-review",
        "filename": "{scene_id}_state_patch_review.json",
        "consumed_by": "canon-patch-json",
    },
    "canon-agent-task": {
        "schema_name": "canon_patch_review.v1",
        "kind": "canon-patch-review",
        "filename": "{scene_id}_canon_patch_review.json",
        "consumed_by": "ready",
    },
}


def semantic_artifact_definition(current_state: str) -> dict[str, str] | None:
    item = SEMANTIC_ARTIFACTS.get(str(current_state or ""))
    return dict(item) if item else None


def semantic_artifact_relative_path(current_state: str, scene_id: str) -> str:
    """Return the project-relative semantic result path for a scene task."""

    definition = semantic_artifact_definition(current_state)
    if definition is None:
        return ""
    filename = definition["filename"].format(scene_id=scene_id)
    if current_state == "roleplay-agent-task":
        return f"branches/{scene_id}/{filename}"
    if current_state == "composition-agent-task":
        return f"drafts/compositions/{filename}"
    if current_state == "state-agent-task":
        return f"characters/state_patches/{filename}"
    if current_state == "canon-agent-task":
        return f"canon/patches/{filename}"
    return ""


def semantic_artifact_contract(current_state: str, scene_id: str) -> dict[str, str] | None:
    definition = semantic_artifact_definition(current_state)
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if definition is None or not relative:
        return None
    return {
        "path": relative,
        "kind": definition["kind"],
        "schema_name": definition["schema_name"],
        "consumed_by": definition["consumed_by"],
        "writeback_policy": "preview-required",
    }


def semantic_artifact_template(current_state: str, scene_id: str, *, source: str = "") -> dict[str, Any]:
    """Build a deliberately incomplete template for the active Agent task."""

    definition = semantic_artifact_definition(current_state)
    if definition is None:
        raise ValueError(f"no semantic artifact is defined for {current_state}")
    common = {
        "scene_id": scene_id,
        "status": "pending_agent_judgment",
        "source_artifact": source,
        "evidence_paths": [],
        "findings": [],
    }
    if current_state == "roleplay-agent-task":
        return {
            "schema": "literary-engineering-workbench/roleplay-result/v1",
            **common,
            "character_actions": [],
            "world_consequences": [],
            "branch_pressures": [],
            "canon_risks": [],
            "writeback_candidates": [],
        }
    if current_state == "composition-agent-task":
        return {
            "schema": "literary-engineering-workbench/composition-review/v1",
            **common,
            "composition_sha256": "",
            "verdict": "pending",
            "required_changes": [],
            "ready_for_generation": False,
        }
    if current_state == "state-agent-task":
        return {
            "schema": "literary-engineering-workbench/state-patch-review/v1",
            **common,
            "state_patch_sha256": "",
            "verdict": "pending",
            "approval_recommendation": "hold",
            "required_changes": [],
        }
    if current_state == "canon-agent-task":
        return {
            "schema": "literary-engineering-workbench/canon-patch-review/v1",
            **common,
            "canon_patch_sha256": "",
            "verdict": "pending",
            "approval_recommendation": "hold",
            "required_changes": [],
        }
    raise ValueError(f"no semantic template is defined for {current_state}")


def write_semantic_artifact_template(
    root: Path,
    current_state: str,
    scene_id: str,
    *,
    source: str = "",
    overwrite: bool = False,
) -> Path:
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if not relative:
        raise ValueError(f"no semantic artifact path is defined for {current_state}")
    path = root.resolve() / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not path.exists():
        path.write_text(
            json.dumps(semantic_artifact_template(current_state, scene_id, source=source), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return path


def semantic_artifact_errors(root: Path, current_state: str, scene_id: str) -> list[str]:
    definition = semantic_artifact_definition(current_state)
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if definition is None or not relative:
        return []
    path = root.resolve() / relative
    if not path.is_file():
        return [f"missing semantic artifact: {relative}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid semantic artifact {relative}: {exc}"]
    if not isinstance(payload, dict):
        return [f"semantic artifact must be a JSON object: {relative}"]
    errors, _warnings = validate_payload(payload, definition["schema_name"])
    messages = [f"semantic artifact {relative} {item.get('path')}: {item.get('message')}" for item in errors]
    if str(payload.get("scene_id") or "") != scene_id:
        messages.append(f"semantic artifact scene_id must be {scene_id}: {relative}")
    if str(payload.get("status") or "").strip().lower() in {"", "pending", "pending_agent_judgment"}:
        messages.append(f"semantic artifact is still pending Agent judgment: {relative}")
    messages.extend(_semantic_quality_errors(root.resolve(), current_state, scene_id, payload, relative))
    return messages


def read_semantic_artifact(root: Path, current_state: str, scene_id: str) -> dict[str, Any]:
    errors = semantic_artifact_errors(root, current_state, scene_id)
    if errors:
        raise ValueError("; ".join(errors))
    relative = semantic_artifact_relative_path(current_state, scene_id)
    payload = json.loads((root.resolve() / relative).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _semantic_quality_errors(
    root: Path,
    current_state: str,
    scene_id: str,
    payload: dict[str, Any],
    relative: str,
) -> list[str]:
    """Reject schema-shaped placeholders that carry no operational judgment."""

    errors: list[str] = []
    status = str(payload.get("status") or "").strip().lower()
    if status != "complete":
        errors.append(f"semantic artifact status must be complete before route advance: {relative}")
        return errors
    evidence = payload.get("evidence_paths")
    if not isinstance(evidence, list) or not [item for item in evidence if str(item).strip()]:
        errors.append(f"semantic artifact must cite at least one evidence path: {relative}")
    if current_state == "roleplay-agent-task":
        for field in ("character_actions", "world_consequences", "branch_pressures"):
            values = payload.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"roleplay semantic artifact requires a non-empty {field}: {relative}")
        return errors

    source_rel = str(payload.get("source_artifact") or "").replace("\\", "/").strip()
    expected = {
        "composition-agent-task": f"drafts/compositions/{scene_id}_composition.json",
        "state-agent-task": f"characters/state_patches/{scene_id}_state_patch.json",
        "canon-agent-task": f"canon/patches/{scene_id}_canon_patch.json",
    }.get(current_state, "")
    if expected and source_rel != expected:
        errors.append(f"semantic artifact source_artifact must be {expected}: {relative}")
    if expected:
        source = root / expected
        if not source.is_file():
            errors.append(f"semantic artifact source is missing: {expected}")
        else:
            digest_key = {
                "composition-agent-task": "composition_sha256",
                "state-agent-task": "state_patch_sha256",
                "canon-agent-task": "canon_patch_sha256",
            }[current_state]
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if str(payload.get(digest_key) or "").lower() != actual:
                errors.append(f"semantic artifact {digest_key} must match exact source: {relative}")
    if str(payload.get("verdict") or "") != "pass":
        errors.append(f"semantic artifact verdict must be pass before route advance: {relative}")
    if current_state == "composition-agent-task" and payload.get("ready_for_generation") is not True:
        errors.append(f"composition semantic artifact must set ready_for_generation=true: {relative}")
    return errors
