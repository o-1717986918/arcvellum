"""Exact semantic artifact projection for the Studio Worker program."""

from __future__ import annotations

import json
from typing import Any

from ..contracts import TaskPackage
from literary_engineering_studio_engine.prompting.agents.schema import load_schema_spec
from literary_engineering_studio_engine.literary.scene.branching.proposals import (
    branch_proposal_contract,
)
from .task_semantic_rendering import render_semantic_output_contract
from .task_semantic_scene_contract import (
    canon_patch_candidate_contract,
    scene_candidate_contract,
    scene_revision_contract,
)
from .task_semantic_workflow_contract import continuity_ledger_contract, state_requirements


def semantic_output_contract(task: TaskPackage) -> dict[str, Any]:
    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    for contract in (
        scene_revision_contract(task, current_state, scene_id),
        scene_candidate_contract(task, current_state, scene_id),
        canon_patch_candidate_contract(task, current_state, scene_id),
        continuity_ledger_contract(current_state, scene_id),
    ):
        if contract:
            return contract
    return _schema_backed_contract(task, current_state, scene_id)


def _schema_backed_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    semantic = task.semantic_artifact
    schema_name = str(semantic.get("schema_name") or "").strip()
    if not schema_name:
        return {}
    schema = _load_schema(schema_name)
    if schema is None:
        return {"path": str(semantic.get("path") or ""), "schema_name": schema_name}
    template = _load_template(task, semantic)
    locked = _locked_values(template)
    contract: dict[str, Any] = {
        "path": str(semantic.get("path") or ""),
        "schema_name": schema_name,
        "required_fields": list(schema.get("required") or []),
        "field_types": dict(schema.get("types") or {}),
        "allowed_values": dict(schema.get("enums") or {}),
        "locked_values": locked,
        "current_state": current_state,
    }
    contract.update(state_requirements(current_state, scene_id, locked))
    if current_state == "branch-agent-task":
        proposals = template.get("proposals")
        count = len(proposals) if isinstance(proposals, list) else 0
        contract["branch_proposal_contract"] = branch_proposal_contract(count)
    return contract


def _load_schema(schema_name: str) -> dict[str, Any] | None:
    try:
        return load_schema_spec(schema_name)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        return None


def _load_template(task: TaskPackage, semantic: dict[str, str]) -> dict[str, Any]:
    path = task.project_root / str(semantic.get("path") or "")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _locked_values(template: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema", "scene_id", "source_artifact", "composition_sha256",
        "state_patch_sha256", "canon_patch_sha256",
    )
    return {
        field: template[field]
        for field in fields
        if field in template and template[field] not in {"", None}
    }


__all__ = ["render_semantic_output_contract", "semantic_output_contract"]
