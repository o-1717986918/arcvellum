"""State, composition, and continuity semantic requirements."""

from __future__ import annotations

from typing import Any


def state_requirements(
    current_state: str,
    scene_id: str,
    locked: dict[str, Any],
) -> dict[str, Any]:
    if current_state == "composition-agent-task":
        composition = f"drafts/compositions/{scene_id}_composition.json"
        return _review_requirements(
            ready_field=("ready_for_generation", True),
            evidence_paths=[composition, f"drafts/compositions/{scene_id}_composition.md"],
            finding="A non-empty list of concrete checked conditions; record positive validation when no defect remains.",
        )
    if current_state in {"state-agent-task", "canon-agent-task"}:
        source_label = "state patch" if current_state == "state-agent-task" else "Canon patch"
        return _review_requirements(
            ready_field=("approval_recommendation", "approve"),
            revision_ready=("approval_recommendation", "hold"),
            evidence_paths=[str(locked.get("source_artifact") or "")],
            finding=(
                f"A non-empty list of concrete evidence-backed checks showing why the {source_label} "
                "is safe to send to its separate approval boundary."
            ),
        )
    return {}


def continuity_ledger_contract(current_state: str, scene_id: str) -> dict[str, Any]:
    if not scene_id:
        return {}
    if current_state == "continuity-ledger-agent-task":
        return {
            "path": f"plot/ledger_deltas/{scene_id}.json",
            "schema_name": "continuity-ledger-delta/v1",
            "required_fields": [
                "schema", "status", "scene_id", "source_draft", "source_draft_sha256",
                "writer_session_id", "evidence_paths", "reader_question_changes",
                "promise_changes", "no_change_reason",
            ],
            "field_types": {
                "evidence_paths": "list", "reader_question_changes": "list",
                "promise_changes": "list", "no_change_reason": "str",
            },
            "allowed_values": {"status": ["complete"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                "scene_id": scene_id,
                "source_draft": f"drafts/scenes/{scene_id}.md",
            },
            "continuity_kind": "delta",
        }
    if current_state == "continuity-ledger-review":
        return {
            "path": f"reviews/continuity/{scene_id}_ledger_review.json",
            "schema_name": "continuity-ledger-review/v1",
            "required_fields": [
                "schema", "status", "scene_id", "delta_path", "delta_sha256",
                "writer_session_id", "reviewer_session_id", "verdict", "findings",
                "required_changes",
            ],
            "field_types": {"findings": "list", "required_changes": "list"},
            "allowed_values": {"status": ["complete"], "verdict": ["pass"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-review/v1",
                "scene_id": scene_id,
                "delta_path": f"plot/ledger_deltas/{scene_id}.json",
            },
            "continuity_kind": "review",
        }
    return {}


def _review_requirements(
    *,
    ready_field: tuple[str, object],
    evidence_paths: list[str],
    finding: str,
    revision_ready: tuple[str, object] | None = None,
) -> dict[str, Any]:
    revision_ready = revision_ready or (ready_field[0], False)
    return {
        "pass_requirements": {
            "status": "complete", "verdict": "pass", ready_field[0]: ready_field[1],
            "required_changes": [], "evidence_paths": evidence_paths, "findings": finding,
        },
        "revision_requirements": {
            "status": "needs_revision", "verdict": "revise_required",
            revision_ready[0]: revision_ready[1],
            "required_changes": "A non-empty list of concrete changes required before a new review.",
        },
    }


__all__ = ["continuity_ledger_contract", "state_requirements"]
