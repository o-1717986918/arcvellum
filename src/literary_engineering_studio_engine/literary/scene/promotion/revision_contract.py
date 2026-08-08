"""Canonical evidence contract for one exact-source prose revision."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...style.anti_ai import lint_ai_style
from ....foundation.draft_text import final_body_from_draft_path


REVISION_SCHEMA = "literary-engineering-workbench/scene-revision/v0.1"
CONTRAST_RULES = {"mechanical-contrast-frame", "contrast-evasion-frame"}
APPLIED_FIELDS = (
    "revision_actions_applied",
    "warnings_addressed",
    "style_notes_addressed",
    "style_adherence_addressed",
)
ROW_FIELDS = (
    "source_excerpt",
    "issue",
    "revised_excerpt",
    "still_uses_explicit_transition",
    "suspected_rephrase",
    "critical_objection",
    "verdict",
)


def revision_source_requires_anti_evasion_rows(
    source: Path,
    *,
    quality_profile: dict[str, object],
    scene_id: str,
) -> bool:
    body = final_body_from_draft_path(source)
    return any(issue.rule in CONTRAST_RULES for issue in lint_ai_style(body, profile=quality_profile, scope=scene_id))


def revision_manifest_errors(
    payload: dict[str, Any],
    *,
    scene_id: str,
    source_rel: str,
    source_sha256: str,
    source_body: str,
    candidate_rel: str,
    candidate_sha256: str,
    candidate_body: str,
    anti_evasion_rows_required: bool,
) -> list[str]:
    errors = _identity_errors(
        payload,
        scene_id=scene_id,
        source_rel=source_rel,
        source_sha256=source_sha256,
        candidate_rel=candidate_rel,
        candidate_sha256=candidate_sha256,
    )
    errors.extend(_state_errors(payload))
    errors.extend(
        _anti_evasion_errors(
            payload,
            source_body=source_body,
            candidate_body=candidate_body,
            rows_required=anti_evasion_rows_required,
        )
    )
    return errors


def _identity_errors(
    payload: dict[str, Any],
    *,
    scene_id: str,
    source_rel: str,
    source_sha256: str,
    candidate_rel: str,
    candidate_sha256: str,
) -> list[str]:
    expected = {
        "schema": REVISION_SCHEMA,
        "scene_id": scene_id,
        "source_candidate": source_rel,
        "source_candidate_sha256": source_sha256,
        "candidate": candidate_rel,
        "candidate_sha256": candidate_sha256,
    }
    return [
        f"revision manifest {key} must equal the exact task value"
        for key, value in expected.items()
        if str(payload.get(key) or "").replace("\\", "/").strip().lower()
        != str(value).replace("\\", "/").strip().lower()
    ]


def _state_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("ready_for_review") is not False:
        errors.append("revision manifest ready_for_review must remain false until independent AgentReview")
    if payload.get("anti_evasion_protocol_applied") is not True:
        errors.append("revision manifest must record anti_evasion_protocol_applied=true")
    if not any(payload.get(field) for field in APPLIED_FIELDS):
        errors.append("revision manifest must record at least one applied review repair")
    if not _empty(payload.get("evasion_risks_unresolved")):
        errors.append("revision manifest has unresolved anti-evasion risks")
    return errors


def _anti_evasion_errors(
    payload: dict[str, Any],
    *,
    source_body: str,
    candidate_body: str,
    rows_required: bool,
) -> list[str]:
    rows = payload.get("anti_evasion_rows")
    rows = rows if isinstance(rows, list) else []
    if not rows:
        if rows_required:
            return ["revision manifest requires anti_evasion_rows for detected contrast/evasion risks"]
        if not str(payload.get("anti_evasion_not_applicable_reason") or "").strip():
            return ["empty anti_evasion_rows requires anti_evasion_not_applicable_reason"]
        return []
    errors: list[str] = []
    retained = False
    for index, value in enumerate(rows):
        row = value if isinstance(value, dict) else {}
        errors.extend(_row_errors(row, index, source_body, candidate_body))
        retained = retained or row.get("verdict") == "retained_with_proof"
    if retained and not _nonempty_list(payload.get("retained_transition_proofs")):
        errors.append("retained transition rows require retained_transition_proofs")
    return errors


def _row_errors(row: dict[str, Any], index: int, source_body: str, candidate_body: str) -> list[str]:
    prefix = f"anti_evasion_rows[{index}]"
    errors = [f"{prefix}.{key} is missing" for key in ROW_FIELDS if not _row_value_present(row, key)]
    source_excerpt = str(row.get("source_excerpt") or "").strip()
    revised_excerpt = str(row.get("revised_excerpt") or "").strip()
    if source_excerpt and source_excerpt not in source_body:
        errors.append(f"{prefix}.source_excerpt is not present in the exact source body")
    if revised_excerpt and revised_excerpt not in candidate_body:
        errors.append(f"{prefix}.revised_excerpt is not present in the revision candidate body")
    verdict = str(row.get("verdict") or "").strip()
    if verdict not in {"resolved", "retained_with_proof"}:
        errors.append(f"{prefix}.verdict must be resolved or retained_with_proof")
    if verdict == "resolved" and (
        row.get("still_uses_explicit_transition") is True or row.get("suspected_rephrase") is True
    ):
        errors.append(f"{prefix} cannot be resolved while transition/evasion risk remains")
    return errors


def _row_value_present(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    return isinstance(value, bool) if key in {"still_uses_explicit_transition", "suspected_rephrase"} else bool(str(value or "").strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def _empty(value: Any) -> bool:
    return value in (None, False, "", [], {})
