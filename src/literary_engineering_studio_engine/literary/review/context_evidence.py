"""Digest-bound compact evidence for exact-candidate scene review."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ...foundation.draft_text import final_body_from_workbench_text
from ...foundation.resources import engine_path
from ..planning.contracts import word_budget_adherence_for_body
from ..planning.narrative_rhythm import (
    narrative_rhythm_contract,
    render_narrative_rhythm_contract,
)
from ..style.anti_ai import render_ai_style_lint_block, style_lint_gate
from .creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
)
from .reader_experience import reader_experience_adherence_for_body


REVIEW_CONTEXT_SCHEMA = (
    "literary-engineering-workbench/scene-review-context/v1"
)
REVIEW_CONTEXT_REVISION = "2026-07-28.1"
REVIEW_CONTEXT_DECLARATION_SCHEMA = (
    "literary-engineering-workbench/scene-review-context-declaration/v1"
)
SCENE_REVIEW_SCHEMA_NAME = "scene_review.v1"


@dataclass(frozen=True)
class SceneReviewEvidence:
    """Candidate-specific evidence shared by the full and compact contracts."""

    scene_id: str
    candidate_path: str
    candidate_sha256: str
    body: str
    style_lint_block: str
    style_lint_gate: dict[str, object]
    word_budget_adherence: dict[str, object]
    reader_adherence: dict[str, Any]
    rhythm_contract: dict[str, Any]
    rhythm_contract_text: str
    quality_profile: dict[str, Any]
    style_mount_snapshot: dict[str, object]
    source_digests: dict[str, str]


def scene_review_context_path(review_json_path: Path) -> Path:
    return review_json_path.with_suffix(".context.json")


def scene_review_context_declaration(
    *,
    scene_id: str,
    candidate_path: str,
    artifact_path: str,
    sidecar_path: str,
    review_json_path: str,
    review_report_path: str,
) -> dict[str, object]:
    schema_path, schema_payload = _scene_review_schema()
    return {
        "schema": REVIEW_CONTEXT_DECLARATION_SCHEMA,
        "revision": REVIEW_CONTEXT_REVISION,
        "scene_id": scene_id,
        "artifact_path": artifact_path,
        "candidate_path": candidate_path,
        "sidecar_path": sidecar_path,
        "review_json_path": review_json_path,
        "review_report_path": review_report_path,
        "output_schema_name": SCENE_REVIEW_SCHEMA_NAME,
        "output_schema_resource_sha256": _file_sha256(schema_path),
        "output_schema_contract_sha256": _canonical_sha256(schema_payload),
    }


def build_scene_review_evidence(
    root: Path,
    *,
    scene_path: Path,
    draft_path: Path,
    composition_path: Path | None,
    style_mount_snapshot: dict[str, object],
    materialization_scope: str,
) -> SceneReviewEvidence:
    root = root.resolve()
    scene_id = scene_path.stem
    draft_text = draft_path.read_text(encoding="utf-8")
    body = final_body_from_workbench_text(draft_text) or draft_text
    quality_profile = load_creative_quality_profile(root)
    rhythm = narrative_rhythm_contract(root, scene_path, composition_path)
    return SceneReviewEvidence(
        scene_id=scene_id,
        candidate_path=_relative(draft_path, root),
        candidate_sha256=_file_sha256(draft_path),
        body=body,
        style_lint_block=render_ai_style_lint_block(
            body,
            profile=quality_profile,
            scope=scene_id,
        ),
        style_lint_gate=style_lint_gate(
            body,
            profile=quality_profile,
            scope=scene_id,
        ),
        word_budget_adherence=word_budget_adherence_for_body(
            root,
            scene_path,
            body,
            materialization_scope=materialization_scope,
        ),
        reader_adherence=reader_experience_adherence_for_body(
            root,
            scene_path,
            body,
        ),
        rhythm_contract=rhythm,
        rhythm_contract_text=render_narrative_rhythm_contract(
            root,
            scene_path,
            composition_path,
        ),
        quality_profile=quality_profile,
        style_mount_snapshot=dict(style_mount_snapshot),
        source_digests=_source_digests(
            root,
            scene_path,
            draft_path,
            composition_path,
        ),
    )


def write_scene_review_context(
    root: Path,
    *,
    evidence: SceneReviewEvidence,
    sidecar_path: Path,
    artifact_path: Path,
    review_json_path: Path,
    review_report_path: Path,
) -> Path:
    root = root.resolve()
    if not sidecar_path.is_file():
        raise FileNotFoundError(
            f"scene review sidecar is missing: {sidecar_path}"
        )
    schema_path, schema_payload = _scene_review_schema()
    payload = {
        "schema": REVIEW_CONTEXT_SCHEMA,
        "revision": REVIEW_CONTEXT_REVISION,
        "scene_id": evidence.scene_id,
        "candidate": {
            "path": evidence.candidate_path,
            "sha256": evidence.candidate_sha256,
        },
        "full_sidecar": {
            "path": _relative(sidecar_path, root),
            "sha256": _file_sha256(sidecar_path),
            "visibility": "exact_on_demand",
        },
        "review_outputs": {
            "json": _relative(review_json_path, root),
            "markdown": _relative(review_report_path, root),
        },
        "output_schema": {
            "name": SCENE_REVIEW_SCHEMA_NAME,
            "resource_sha256": _file_sha256(schema_path),
            "contract_sha256": _canonical_sha256(schema_payload),
            "contract": schema_payload,
        },
        "style_mount_snapshot": evidence.style_mount_snapshot,
        "creative_quality_profile": _quality_identity(
            root,
            evidence.quality_profile,
        ),
        "deterministic_evidence": {
            "style_lint": evidence.style_lint_gate,
            "word_budget": evidence.word_budget_adherence,
            "reader_experience": evidence.reader_adherence,
            "narrative_rhythm": _compact_rhythm(evidence.rhythm_contract),
        },
        "review_policy": _review_policy(),
        "source_digests": evidence.source_digests,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact_path


def _compact_rhythm(contract: Mapping[str, Any]) -> dict[str, Any]:
    rhythm = _mapping(contract.get("narrative_rhythm"))
    bridge = _mapping(contract.get("scene_bridge"))
    return {
        "schema": contract.get("schema"),
        "status": contract.get("status"),
        "source": contract.get("source"),
        "plan_revision": contract.get("plan_revision"),
        "plan_digest": contract.get("plan_digest"),
        "missing_required": contract.get("missing_required", []),
        "narrative_rhythm": {
            key: rhythm.get(key)
            for key in (
                "rhythm_role",
                "pace",
                "density",
                "detail_level",
                "scene_turn",
                "scene_function",
                "reader_effect",
                "narrative_distance",
                "tension_curve",
                "slow_down_points",
                "speed_up_points",
                "texture_variety",
                "chapter_ending_policy",
            )
        },
        "scene_bridge": {
            key: bridge.get(key)
            for key in (
                "incoming_pressure",
                "incoming_from_previous",
                "reader_questions_carried",
                "outgoing_hooks",
                "outgoing_hook",
                "promise_payoff_items",
                "continuity_handshake",
            )
        },
    }


def _quality_identity(
    root: Path,
    profile: Mapping[str, Any],
) -> dict[str, object]:
    return {
        "path": (
            _relative(creative_quality_profile_path(root), root)
            if creative_quality_profile_exists(root)
            else "implicit-default"
        ),
        "profile_id": str(profile.get("profile_id") or ""),
        "name": str(profile.get("name") or ""),
        "preset": str(profile.get("preset") or ""),
        "revision": int(profile.get("revision") or 1),
        "digest": str(profile.get("digest") or ""),
    }


def _review_policy() -> dict[str, object]:
    return {
        "allowed_conclusions": [
            "pass",
            "pass_with_notes",
            "revise_required",
            "reject",
        ],
        "clean_pass": {
            "word_budget_status": ["pass", "not_required"],
            "reader_experience_status": ["pass", "not_required"],
            "rhythm_status": ["pass", "not_applicable"],
            "new_character_status": [
                "none",
                "existing_only",
                "ephemeral_only",
                "resolved",
            ],
            "requires_no_actionable": [
                "blocking_issues",
                "revision_actions",
                "warnings where blocks_pass is not false",
                "style_adherence.deviations where blocks_pass is not false",
                "style_adherence.revision_actions",
            ],
            "informational_evidence_allowed": [
                "style_notes",
                "low/info warnings with blocks_pass=false",
                "below-threshold style deviations with blocks_pass=false",
            ],
        },
        "anti_evasion_required": True,
        "independent_reviewer_required": True,
        "canon_writeback_required": True,
    }


def _source_digests(
    root: Path,
    scene_path: Path,
    draft_path: Path,
    composition_path: Path | None,
) -> dict[str, str]:
    paths = [
        scene_path,
        draft_path,
        composition_path,
        root / "plot" / "word_budget" / "word_budget.json",
        root / "plot" / "rhythm_plan.json",
        root / "style" / "creative_quality_profile.json",
        root / "style" / "style-profile.md",
    ]
    return {
        _relative(path, root): _file_sha256(path)
        for path in paths
        if path is not None and path.is_file()
    }


def _scene_review_schema() -> tuple[Path, dict[str, Any]]:
    path = engine_path(
        "schemas",
        "agent_outputs",
        f"{SCENE_REVIEW_SCHEMA_NAME}.schema.json",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_id") != SCENE_REVIEW_SCHEMA_NAME
        or payload.get("schema_value")
        != "literary-engineering-workbench/scene-review-agent/v1"
    ):
        raise ValueError("embedded scene review output schema is invalid")
    return path, payload


def _relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"scene review evidence path is outside the project: {path}"
        ) from exc


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(payload: object) -> str:
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "REVIEW_CONTEXT_DECLARATION_SCHEMA",
    "REVIEW_CONTEXT_REVISION",
    "REVIEW_CONTEXT_SCHEMA",
    "SceneReviewEvidence",
    "build_scene_review_evidence",
    "scene_review_context_declaration",
    "scene_review_context_path",
    "write_scene_review_context",
]
