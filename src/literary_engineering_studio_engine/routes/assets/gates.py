"""Deterministic lifecycle Gates for candidate project assets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES
from ...literary.assets.promotion import approval_gate_errors as _shared_approval_gate_errors
from ...literary.assets.promotion import approval_matches_file as _shared_approval_matches_file
from ...literary.assets.promotion import candidate_review_gate_errors as _shared_review_gate_errors
from ...task_paths import read_json as _read_json
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path
from .evidence import (
    asset_type_from_payload_or_path,
    candidate_path_for_id,
    candidate_path_for_task,
    file_sha256,
    read_optional_json,
)


GateValidator = Callable[[Path, dict[str, object], Path, str], list[str]]


SUCCESS_NOTES = {
    "asset-creation-agent-task": "asset candidate creation gate passed",
    "asset-review-task-file": "asset candidate creation gate passed",
    "asset-review-agent-task": "asset review verdict recorded; pass or formal revision routing may continue",
    "asset-review-pass": "asset candidate revised and prior review evidence reset for independent recheck",
    "asset-approval-revision": "asset candidate revised and prior review evidence reset for independent recheck",
    "asset-promotion": "asset promotion gate passed",
}


def asset_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    candidate = candidate_path_for_task(root, task)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or candidate.stem)
    validator = GATE_VALIDATORS.get(current_state)
    errors = validator(root, task, candidate, candidate_id) if validator else []
    note = SUCCESS_NOTES.get(current_state)
    return errors, [note] if note and not errors else []


def _intake(root: Path, _task: dict[str, object], _candidate: Path, _candidate_id: str) -> list[str]:
    return asset_intake_gate_errors(root)


def _creation(root: Path, _task: dict[str, object], candidate: Path, _candidate_id: str) -> list[str]:
    return asset_creation_gate_errors(root, candidate)


def _review_prepare(root: Path, _task: dict[str, object], candidate: Path, candidate_id: str) -> list[str]:
    errors = asset_creation_gate_errors(root, candidate)
    review_task = root / "reviews" / "assets" / f"{candidate_id}_review.agent_tasks.md"
    if not review_task.exists():
        errors.append(f"asset review sidecar missing: {_rel(review_task, root)}")
    return errors


def _review_execute(root: Path, _task: dict[str, object], candidate: Path, candidate_id: str) -> list[str]:
    errors = asset_creation_gate_errors(root, candidate)
    errors.extend(task_review_gate_errors(root, candidate, candidate_id, require_pass=False))
    return errors


def _revision(root: Path, task: dict[str, object], candidate: Path, candidate_id: str) -> list[str]:
    errors = asset_creation_gate_errors(root, candidate)
    errors.extend(asset_revision_gate_errors(root, task, candidate, candidate_id))
    return errors


def _approval(root: Path, _task: dict[str, object], candidate: Path, candidate_id: str) -> list[str]:
    errors = asset_creation_gate_errors(root, candidate)
    errors.extend(task_review_gate_errors(root, candidate, candidate_id, require_pass=True))
    errors.extend(asset_approval_gate_errors(root, candidate_id, candidate))
    return errors


def _promotion(root: Path, _task: dict[str, object], candidate: Path, candidate_id: str) -> list[str]:
    errors = asset_creation_gate_errors(root, candidate)
    errors.extend(task_review_gate_errors(root, candidate, candidate_id, require_pass=True))
    errors.extend(asset_approval_gate_errors(root, candidate_id, candidate))
    errors.extend(asset_promotion_gate_errors(root, candidate_id))
    return errors


GATE_VALIDATORS: dict[str, GateValidator] = {
    "asset-intake": _intake,
    "asset-creation-agent-task": _creation,
    "asset-review-task-file": _review_prepare,
    "asset-review-agent-task": _review_execute,
    "asset-review-pass": _revision,
    "asset-approval-revision": _revision,
    "asset-approval": _approval,
    "asset-promotion": _promotion,
}


def asset_intake_gate_errors(root: Path) -> list[str]:
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if not base.exists():
            continue
        if any(base.glob("*.agent_tasks.md")) or any(base.glob("*.json")):
            return []
    return ["no candidate asset or asset creation sidecar exists; run seed-project-assets first"]


def asset_creation_gate_errors(root: Path, candidate: Path) -> list[str]:
    task_path = candidate.with_suffix(".agent_tasks.md")
    report_path = candidate.with_suffix(".md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset creation sidecar is incomplete: {state.get('message')}")
    payload, error = read_optional_json(candidate)
    if error:
        errors.append(error)
    else:
        errors.extend(_candidate_payload_errors(root, candidate, payload))
    if not report_path.exists():
        errors.append(f"asset candidate report missing: {_rel(report_path, root)}")
    return errors


def _candidate_payload_errors(root: Path, candidate: Path, payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    asset_type = asset_type_from_payload_or_path(root, candidate, payload)
    schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
    if not schema_name:
        errors.append(f"unknown asset type for candidate: {asset_type or _rel(candidate, root)}")
    else:
        schema_errors, _warnings = validate_payload(payload, schema_name)
        errors.extend(f"asset candidate schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    if not str(payload.get("candidate_id") or "").strip():
        errors.append("asset candidate JSON must contain candidate_id")
    if not isinstance(payload.get("risks"), list):
        errors.append("asset candidate JSON must contain risks list")
    if not isinstance(payload.get("source_paths"), list):
        errors.append("asset candidate JSON must contain source_paths list")
    if not isinstance(payload.get("promotion_notes"), str) or not str(payload.get("promotion_notes") or "").strip():
        errors.append("asset candidate JSON must contain promotion_notes")
    return errors


def asset_review_gate_errors(
    root: Path,
    candidate_id: str,
    *,
    require_pass: bool,
    candidate: Path | None = None,
    asset_type: str = "",
) -> list[str]:
    candidate_path = candidate or candidate_path_for_id(root, candidate_id)
    payload = _read_json(candidate_path)
    resolved_type = asset_type or asset_type_from_payload_or_path(root, candidate_path, payload)
    return _shared_review_gate_errors(root, candidate_path, asset_type=resolved_type, require_pass=require_pass)


def task_review_gate_errors(
    root: Path,
    candidate: Path,
    candidate_id: str,
    *,
    require_pass: bool,
) -> list[str]:
    asset_type = asset_type_from_payload_or_path(root, candidate, _read_json(candidate))
    return asset_review_gate_errors(
        root,
        candidate_id,
        require_pass=require_pass,
        candidate=candidate,
        asset_type=asset_type,
    )


def asset_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    candidate: Path,
    candidate_id: str,
) -> list[str]:
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(review_task)
    errors = _candidate_revision_errors(root, task, candidate)
    errors.extend(_review_revision_errors(review_json, candidate_id))
    errors.extend(_completion_revision_errors(root, completion, review_task))
    errors.extend(_revision_report_errors(root, candidate, review))
    return errors


def _candidate_revision_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    previous_hash = str(task.get("candidate_sha256_before_revision") or "").strip().lower()
    if not previous_hash:
        return ["asset revision task is missing candidate_sha256_before_revision provenance"]
    if not candidate.is_file():
        return [f"asset candidate missing after revision: {_rel(candidate, root)}"]
    if file_sha256(candidate) == previous_hash:
        return ["asset candidate content did not change; review labels cannot substitute for a real revision"]
    return []


def _review_revision_errors(review_json: Path, candidate_id: str) -> list[str]:
    payload, error = read_optional_json(review_json)
    if error:
        return [error]
    errors: list[str] = []
    status = str(payload.get("status") or "").strip().lower()
    if status != "recheck_required":
        errors.append(f"revised asset review status must be recheck_required; got {status or 'missing'}")
    candidate_ref = str(payload.get("candidate") or "").strip()
    if candidate_ref and Path(candidate_ref).stem != candidate_id:
        errors.append(f"asset revision candidate mismatch: {candidate_ref} does not match {candidate_id}")
    applied = payload.get("applied_revision_actions")
    if not isinstance(applied, list) or not applied:
        errors.append("revised asset review must record non-empty applied_revision_actions")
    round_value = payload.get("revision_round")
    if not isinstance(round_value, int) or isinstance(round_value, bool) or round_value < 1:
        errors.append("revised asset review must record revision_round as an integer >= 1")
    return errors


def _completion_revision_errors(root: Path, completion: Path, review_task: Path) -> list[str]:
    payload, error = read_optional_json(completion)
    if error:
        return [error]
    errors: list[str] = []
    status = str(payload.get("status") or "").strip().lower()
    if status != "recheck_required":
        errors.append(f"asset review completion status must be recheck_required after revision; got {status or 'missing'}")
    if payload.get("expected_artifacts_checked") is not False:
        errors.append("asset review completion expected_artifacts_checked must be false until fresh review")
    expected_source = _rel(review_task, root)
    source_task = str(payload.get("source_task") or "").replace("\\", "/")
    if source_task != expected_source:
        errors.append(f"asset review completion source_task must be {expected_source}")
    return errors


def _revision_report_errors(root: Path, candidate: Path, review: Path) -> list[str]:
    errors: list[str] = []
    for path, label in ((candidate.with_suffix(".md"), "candidate report"), (review, "asset review report")):
        if not path.exists():
            errors.append(f"{label} missing: {_rel(path, root)}")
    return errors


def asset_approval_gate_errors(root: Path, candidate_id: str, candidate: Path) -> list[str]:
    return _shared_approval_gate_errors(root, candidate_id, candidate)


def approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    return _shared_approval_matches_file(approval, subject)


def asset_promotion_gate_errors(root: Path, candidate_id: str) -> list[str]:
    manifest = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    report = manifest.with_suffix(".md")
    payload, error = read_optional_json(manifest)
    if error:
        return [error]
    errors: list[str] = []
    if payload.get("status") != "promoted":
        errors.append(f"asset promotion status must be promoted; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved"):
        errors.append("asset promotion used allow_unapproved; formal Skill-host route must not use approval bypass")
    if str(payload.get("candidate_id") or "") != candidate_id:
        errors.append(f"asset promotion candidate_id mismatch: {payload.get('candidate_id') or 'missing'}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), list) else []
    if not outputs:
        errors.append("asset promotion manifest must list outputs")
    for item in outputs:
        path = _resolve_project_path(root, str(item))
        if not path.exists():
            errors.append(f"asset promotion output missing: {_rel(path, root)}")
    if not report.exists():
        errors.append(f"asset promotion report missing: {_rel(report, root)}")
    return errors
