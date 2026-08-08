"""Formal branch manifest and selection evidence gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...flow_gates import branch_selection_status, fallback_selection_reason_error
from ...semantic_task_contracts import (
    semantic_artifact_errors,
    semantic_artifact_relative_path,
    validated_branch_proposal_ids,
)
from ...task_paths import relative_path as _rel
from ...scene_route_support import _read_optional_json


def branch_manifest_gate_errors(root: Path, scene_id: str, *, require_agent_proposals: bool = False) -> list[str]:
    path = root / "branches" / scene_id / "branch_manifest.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"branch manifest is missing or empty: {_rel(path, root)}"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    if str(provenance.get("created_by") or "") != "branch-simulate":
        return ["branch manifest lacks formal_cli_provenance.created_by=branch-simulate; run branch-simulate --agent instead of hand-writing the manifest"]
    if provenance.get("agent_tasks_requested") is not True:
        return ["branch manifest was not created with --agent; branch sidecar is required for formal route"]
    roleplay_result = semantic_artifact_relative_path("roleplay-agent-task", scene_id)
    if str(payload.get("roleplay_result") or "").replace("\\", "/") != roleplay_result:
        return ["branch manifest does not declare the exact roleplay_result consumed by branch-simulate"]
    evidence = payload.get("roleplay_evidence")
    if not isinstance(evidence, dict) or str(evidence.get("status") or "") != "complete":
        return ["branch manifest does not contain completed roleplay semantic evidence"]
    if require_agent_proposals:
        return semantic_artifact_errors(root, "branch-agent-task", scene_id)
    return []


def branch_selection_gate(root: Path, scene_id: str) -> tuple[list[str], list[str]]:
    selection = root / "branches" / scene_id / "branch_selection.md"
    branch_state = branch_selection_status(selection)
    if branch_state.get("status") != "selected":
        return [str(branch_state.get("message") or "branch selection is not selected")], []
    manifest = root / "branches" / scene_id / "branch_manifest.json"
    payload, error = _read_optional_json(manifest)
    if error:
        return [error], []
    fallback_ids = _fallback_branch_ids(payload)
    try:
        proposal_ids = validated_branch_proposal_ids(root, scene_id, payload)
    except ValueError as exc:
        return [str(exc)], []
    branch_ids = fallback_ids | proposal_ids
    selected = str(branch_state.get("selected_branch") or "").strip()
    if not branch_ids:
        return [f"branch manifest has no selectable branches: {_rel(manifest, root)}"], []
    if selected not in branch_ids:
        return [f"selected_branch `{selected}` is not present in validated Agent proposals or {_rel(manifest, root)}"], []
    fallback_error = fallback_selection_reason_error(branch_state, selected, proposal_ids, fallback_ids)
    if fallback_error:
        return [fallback_error], []
    if proposal_ids and selected in fallback_ids:
        reason = str(branch_state.get("fallback_reason") or "").strip()
        return [], [f"branch selection: {selected} (deterministic fallback: {reason})"]
    origin = "agent-proposal" if selected in proposal_ids else "deterministic-fallback"
    return [], [f"branch selection: {selected} ({origin})"]


def _fallback_branch_ids(payload: dict[str, Any]) -> set[str]:
    branches = payload.get("branches") if isinstance(payload, dict) else None
    return {
        str(item.get("branch_id") or item.get("id") or "").strip()
        for item in branches
        if isinstance(item, dict)
    } if isinstance(branches, list) else set()
