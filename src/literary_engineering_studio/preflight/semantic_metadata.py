"""Machine-owned identity normalization for semantic artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from literary_engineering_studio_engine.public.prompting import load_schema_spec
from literary_engineering_studio_engine.public.tasking import (
    semantic_artifact_definition,
    semantic_artifact_relative_path,
)


SEMANTIC_SOURCE_PATTERNS = {
    "roleplay-agent-task": "branches/{scene_id}/roleplay_simulation.md",
    "branch-agent-task": "branches/{scene_id}/branch_manifest.json",
    "composition-agent-task": "drafts/compositions/{scene_id}_composition.json",
    "state-agent-task": "characters/state_patches/{scene_id}_state_patch.json",
    "canon-agent-task": "canon/patches/{scene_id}_canon_patch.json",
}

STATUS_ALIASES = {
    "completed": "complete",
    "done": "complete",
    "passed": "complete",
    "pass": "complete",
}


def canonicalize_semantic_artifact_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    read_object: Callable[[Path], dict[str, Any] | None],
    write_machine_fields: Callable[..., list[dict[str, str]]],
    canonicalize_declared_list_fields: Callable[..., list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Normalize transport identity while preserving Agent-authored judgment."""

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    definition = semantic_artifact_definition(current_state)
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if definition is None or not relative:
        return []
    path = sandbox.workspace / Path(relative)
    payload = read_object(path)
    if payload is None:
        return []
    schema_spec = load_schema_spec(definition["schema_name"])
    expected = _expected_machine_fields(current_state, scene_id, payload, schema_spec, sandbox)
    changes = write_machine_fields(path, relative, payload, expected, "semantic-artifact")
    list_changes = canonicalize_declared_list_fields(path, relative, payload, schema_spec)
    return [*changes, *list_changes]


def _expected_machine_fields(
    current_state: str,
    scene_id: str,
    payload: dict[str, Any],
    schema_spec: dict[str, Any],
    sandbox: SandboxManifest,
) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "schema": str(schema_spec.get("schema_value") or payload.get("schema") or ""),
        "scene_id": scene_id,
    }
    _bind_source_artifact(expected, current_state, scene_id, sandbox)
    actual_status = str(payload.get("status") or "").strip().lower()
    if actual_status in STATUS_ALIASES:
        expected["status"] = STATUS_ALIASES[actual_status]
    if _composition_verdict_is_lifecycle_alias(current_state, payload):
        expected["verdict"] = "pass"
    return expected


def _bind_source_artifact(
    expected: dict[str, Any],
    current_state: str,
    scene_id: str,
    sandbox: SandboxManifest,
) -> None:
    source_pattern = SEMANTIC_SOURCE_PATTERNS.get(current_state, "")
    expected_source = source_pattern.format(scene_id=scene_id)
    if not expected_source:
        return
    expected["source_artifact"] = expected_source
    source_path = sandbox.workspace / Path(expected_source)
    digest_key = {
        "composition-agent-task": "composition_sha256",
        "state-agent-task": "state_patch_sha256",
        "canon-agent-task": "canon_patch_sha256",
    }.get(current_state, "")
    if source_path.is_file() and digest_key:
        expected[digest_key] = hashlib.sha256(source_path.read_bytes()).hexdigest()


def _composition_verdict_is_lifecycle_alias(current_state: str, payload: dict[str, Any]) -> bool:
    return (
        current_state == "composition-agent-task"
        and str(payload.get("verdict") or "").strip().lower() in {"complete", "completed"}
        and payload.get("ready_for_generation") is True
        and not payload.get("required_changes")
    )
