"""Scene prose, revision, and Canon semantic output contracts."""

from __future__ import annotations

from typing import Any

from ..contracts import TaskPackage
from ..protocols.scene_artifacts import is_scene_revision_manifest_path
from literary_engineering_studio_engine.public.prompting import load_schema_spec
from literary_engineering_studio_engine.public.tasking import SCENE_REVISION_STATES


def scene_review_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    if current_state not in {"candidate-review", "agent-review-task"}:
        return {}
    path = next(
        (
            item for item in task.expected_outputs
            if item.endswith(".json")
            and "scene_review" in item
            and not item.endswith(".agent_completion.json")
        ),
        "",
    )
    if not path:
        return {}
    schema = load_schema_spec("scene_review.v1")
    required = [str(item) for item in schema.get("required") or []]
    formal_required = ["reviewer_session_id"]
    model_owned = list(dict.fromkeys([*required, *formal_required]))
    return {
        "path": path,
        "schema_name": "scene_review.v1",
        "schema_value": str(schema.get("schema_value") or ""),
        "required_fields": model_owned,
        "field_types": dict(schema.get("types") or {}),
        "allowed_values": dict(schema.get("enums") or {}),
        "object_shapes": dict(schema.get("object_shapes") or {}),
        "model_owned_fields": model_owned,
        "studio_owned_fields": [],
        "locked_values": {
            "schema": str(schema.get("schema_value") or ""),
            "scene_id": scene_id,
        },
    }


def scene_revision_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    if current_state not in SCENE_REVISION_STATES:
        return {}
    path = next(
        (item for item in task.expected_outputs if is_scene_revision_manifest_path(item)),
        "",
    )
    if not path:
        return {}
    required_fields = [
        "revision_actions_applied", "warnings_addressed", "style_notes_addressed",
        "style_adherence_addressed", "anti_evasion_rows", "retained_transition_proofs",
        "evasion_risks_unresolved", "new_character_register", "waivers",
    ]
    return {
        "path": path,
        "schema_name": "scene-revision/v1",
        "revision_kind": "exact-source",
        "required_fields": required_fields,
        "field_types": {
            "revision_actions_applied": "list",
            "warnings_addressed": "list",
            "style_notes_addressed": "list",
            "style_adherence_addressed": "list",
            "anti_evasion_rows": "list",
            "anti_evasion_not_applicable_reason": "str",
            "retained_transition_proofs": "list",
            "evasion_risks_unresolved": "list",
            "new_character_register": "dict",
            "waivers": "list",
        },
        "object_shapes": {
            "anti_evasion_rows[]": {
                "source_excerpt": "exact excerpt present in revision_source",
                "issue": "specific review or lint defect",
                "revised_excerpt": "exact excerpt present in the revised candidate",
                "still_uses_explicit_transition": "bool",
                "suspected_rephrase": "bool",
                "critical_objection": "critical attempt to disprove the repair",
                "verdict": "resolved | retained_with_proof",
            },
            "new_character_register": new_character_register_shape("revision"),
        },
        "model_owned_fields": [*required_fields, "anti_evasion_not_applicable_reason"],
        "studio_owned_fields": [
            "schema", "scene_id", "source_candidate", "source_candidate_sha256", "candidate",
            "candidate_sha256", "report", "source_paths", "prompt_manifest",
            "style_mount_snapshot", "creative_quality_profile_digest",
            "reader_experience_contract", "narrative_rhythm_contract",
            "historical_context_snapshot",
            "anti_evasion_protocol_applied", "ready_for_review", "generated_by", "provider",
            "formal_contract_revision", "writer_session_id",
        ],
        "locked_values": {"scene_id": scene_id},
    }


def scene_candidate_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    if current_state not in {"candidate-generation-provenance", "generation-agent-task"}:
        return {}
    path = next(
        (
            item for item in task.expected_outputs
            if item.endswith(".json")
            and not item.endswith(".prompt.json")
            and not item.endswith(".agent_completion.json")
        ),
        "",
    )
    if not path:
        return {}
    model_fields = [
        "word_budget_standard_applied", "pass_with_notes_actions_applied",
        "canon_writeback", "new_character_register",
    ]
    return {
        "path": path,
        "schema_name": "scene-candidate/v1",
        "required_fields": model_fields,
        "field_types": {
            "word_budget_standard_applied": "bool",
            "pass_with_notes_actions_applied": "bool",
            "canon_writeback": "dict",
            "new_character_register": "dict",
        },
        "object_shapes": {
            "canon_writeback": {
                "canon_change": "true | false | unknown",
                "no_canon_change_reason": "required non-empty str when canon_change=false",
                "candidate_patch": "optional project-relative str",
            },
            "new_character_register": new_character_register_shape("generation"),
        },
        "model_owned_fields": model_fields,
        "studio_owned_fields": [
            "schema", "scene_id", "candidate", "prompt_manifest", "generated_by", "provider",
            "formal_contract_revision", "writer_session_id", "style_mount_snapshot",
            "creative_quality_profile_digest", "reader_experience_contract",
            "narrative_rhythm_contract", "style_generation_standard_applied",
            "hard_constraints_applied", "anti_evasion_protocol_applied",
            "narrative_rhythm_standard_applied",
        ],
        "locked_values": {"scene_id": scene_id},
    }


def canon_patch_candidate_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    if current_state != "canon-patch-json" or not scene_id:
        return {}
    path = next(
        (item for item in task.expected_outputs if item.endswith("_canon_patch.json")), ""
    )
    if not path:
        return {}
    scene = str(task.payload.get("scene") or f"scenes/{scene_id}.yaml")
    source = f"drafts/scenes/{scene_id}.md"
    return {
        "path": path,
        "schema_name": "canon-patch-candidate/v0.1",
        "required_fields": ["canon_change", "no_canon_change_reason", "items"],
        "field_types": {"canon_change": "bool", "no_canon_change_reason": "str", "items": "list"},
        "allowed_values": {"canon_change": [True, False]},
        "object_shapes": {
            "items[]": {
                "type": "durable fact category",
                "summary": "one precise persistent world fact",
                "source_evidence": "exact prose evidence or precise evidence locator",
                "target_files": "non-empty list of project-relative Canon targets",
                "risk_level": "low | medium | high",
                "requires_user_approval": "bool",
            }
        },
        "model_owned_fields": ["canon_change", "no_canon_change_reason", "items"],
        "studio_owned_fields": [
            "schema", "formal_contract_revision", "scene_id", "created_at", "scene", "source",
            "status", "applied", "requires_user_approval", "source_paths",
        ],
        "locked_values": {
            "schema": "literary-engineering-workbench/canon-patch-candidate/v0.1",
            "formal_contract_revision": "2026-07-23.3",
            "scene_id": scene_id,
            "scene": scene,
            "source": source,
            "status": "candidate",
            "applied": False,
            "requires_user_approval": True,
            "source_paths": [scene, source],
        },
        "canon_candidate_kind": "durable-world-fact-classification",
    }


def new_character_register_shape(stage: str) -> dict[str, str]:
    blocking = "list; must be empty for a clean revision" if stage == "revision" else (
        "list; must be empty for a clean generation result"
    )
    return {
        "schema": "literary-engineering-workbench/new-character-register/v0.1",
        "status": "none | existing_only | ephemeral_only | candidates_ready | resolved",
        "introduced": "list",
        "ephemeral_waivers": "list",
        "blocking_issues": blocking,
    }


__all__ = [
    "canon_patch_candidate_contract",
    "scene_candidate_contract",
    "scene_review_contract",
    "scene_revision_contract",
]
