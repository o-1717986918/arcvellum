"""TaskPackage and machine-owned metadata assembly for asset engineering."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.prompting.agents.schema import compact_schema_contract
from literary_engineering_studio_engine.literary.assets.workshop import ASSET_SCHEMA_NAMES
from literary_engineering_studio_engine.tasking.paths import resolve_project_path as _resolve_project_path
from ...tasking.builder import TaskBuilder
from .blueprints import asset_blueprint_for_state
from .evidence import candidate_digest, file_sha256


DEFAULT_REQUIRED_READING = [
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "references/agent-run-protocol.md",
    "references/cli-run-protocol.md",
]

FORBIDDEN_SHORTCUTS = [
    "Do not write directly into canon/, characters/, plot/outline.md, scenes/, drafts/, exports/, or releases/ from a candidate task.",
    "Do not promote any candidate asset without a clean Worker asset review and an approve record.",
    "Do not use --allow-unapproved or any debug approval bypass in formal Studio work.",
    "Do not let extracted/source-derived claims become canon without evidence_refs, confidence, review, and approval.",
    "Do not treat this task as complete until task-submit and task-complete have succeeded.",
]


def build_asset_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    candidate_id = str(state.get("candidate_id") or state.get("target_id") or "asset-intake")
    asset_type = str(state.get("asset_type") or "")
    candidate = str(state.get("candidate") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = asset_blueprint_for_state(root, candidate_id, asset_type, candidate, current_state, next_action)
    payload = TaskBuilder(
        root=root,
        route=route,
        target_id=candidate_id,
        scene_id=candidate_id,
        current_state=current_state,
        blueprint=blueprint,
        required_reading=DEFAULT_REQUIRED_READING,
        forbidden_shortcuts=FORBIDDEN_SHORTCUTS,
        route_fields={
            "candidate_id": candidate_id,
            "asset_type": asset_type,
            "candidate": candidate,
        },
    ).build()
    payload.setdefault("core_managed_outputs", [])
    payload["system_owned_fields"] = asset_system_owned_fields(
        candidate_id=candidate_id,
        asset_type=asset_type,
        candidate=candidate,
        current_state=current_state,
        source_paths=[str(item) for item in payload["source_paths"]],
        expected_outputs=[str(item) for item in payload["expected_outputs"]],
        candidate_sha256=candidate_digest(root, candidate),
    )
    if current_state in {"asset-review-pass", "asset-approval-revision"} and candidate:
        candidate_path = _resolve_project_path(root, candidate)
        if candidate_path.is_file():
            payload["candidate_sha256_before_revision"] = file_sha256(candidate_path)
    return payload


def asset_system_owned_fields(
    *,
    candidate_id: str,
    asset_type: str,
    candidate: str,
    current_state: str,
    source_paths: list[str],
    expected_outputs: list[str],
    candidate_sha256: str = "",
) -> dict[str, object]:
    schema_contract = _asset_schema_contract(asset_type)
    review_json = next(
        (
            item
            for item in expected_outputs
            if item.replace("\\", "/").startswith("reviews/assets/") and item.endswith("_review.json")
        ),
        f"reviews/assets/{candidate_id}_review.json",
    )
    completion_status = "recheck_required" if current_state in {"asset-review-pass", "asset-approval-revision"} else "complete"
    review_statuses = ["recheck_required"] if completion_status == "recheck_required" else ["pass", "failed", "revise_required"]
    return {
        "contract_version": "v1",
        "candidate": {
            "path": candidate,
            "candidate_id": candidate_id,
            "asset_type": asset_type,
            "schema": str(schema_contract.get("schema_value") or ""),
            "schema_contract": schema_contract,
            "source_paths": source_paths,
        },
        "review": {
            "path": review_json,
            "schema": "literary-engineering-workbench/candidate-asset-review/v0.1",
            "candidate": candidate,
            "candidate_id": candidate_id,
            "asset_type": asset_type,
            "candidate_sha256": candidate_sha256,
        },
        "completion": {
            "schema": "literary-engineering-workbench/agent-task-completion/v1",
            "status": completion_status,
            "expected_artifacts_checked": completion_status == "complete",
        },
        "enums": {
            "asset_review.status": review_statuses,
            "asset_revision.review_status": ["recheck_required"],
            "completion.status": ["complete", "recheck_required"],
        },
    }


def _asset_schema_contract(asset_type: str) -> dict[str, object]:
    schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
    if not schema_name:
        return {}
    try:
        return compact_schema_contract(schema_name)
    except (OSError, ValueError):
        return {}
