"""Project-level revision, longform audit, and committee Gates."""

from __future__ import annotations

from pathlib import Path

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status, default_agent_completion_path
from ...literary.review.longform_contract import longform_audit_gate_errors
from ...literary.review.project_targets import project_review_repair_target_issues
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path
from .canon_gates import canon_lint_gate_errors
from .evidence import file_sha256, read_optional_json


def project_review_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    review_kind: str,
) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    errors = _revision_target_errors(root, task, targets, review_kind)
    errors.extend(_review_reset_errors(root, "canon_review"))
    errors.extend(canon_lint_gate_errors(root, require_clean=True, require_current_contract=True))
    if review_kind == "committee":
        errors.extend(_review_reset_errors(root, "committee_project-final-audit"))
        errors.extend(longform_audit_file_gate_errors(root))
    return errors


def _revision_target_errors(
    root: Path,
    task: dict[str, object],
    targets: list[str],
    review_kind: str,
) -> list[str]:
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    errors: list[str] = []
    if not targets:
        errors.append(f"{review_kind} revision has no declared repair_targets; reviewer must provide exact target_path values")
    changed = False
    for relative in targets:
        path = _resolve_project_path(root, relative)
        if not path.is_file():
            errors.append(f"declared review repair target missing after revision: {relative}")
            continue
        previous = str(hashes.get(relative) or "")
        if not previous or file_sha256(path) != previous:
            changed = True
    if targets and not changed:
        errors.append("project review repair did not change any declared repair target")
    return errors


def _review_reset_errors(root: Path, prefix: str) -> list[str]:
    json_path = root / "reviews" / "agent" / f"{prefix}.json"
    task_path = json_path.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(task_path)
    errors = _review_payload_reset_errors(json_path, prefix)
    errors.extend(_completion_reset_errors(completion, prefix))
    return errors


def _review_payload_reset_errors(json_path: Path, prefix: str) -> list[str]:
    payload, error = read_optional_json(json_path)
    if error:
        return [error]
    errors: list[str] = []
    field = "conclusion" if prefix == "canon_review" else "final_recommendation"
    status = str(payload.get(field) or "").strip().lower()
    if status != "recheck_required":
        errors.append(f"{prefix} {field} must be recheck_required after revision; got {status or 'missing'}")
    applied = payload.get("applied_repair_actions")
    if not isinstance(applied, list) or not applied:
        errors.append(f"{prefix} must record non-empty applied_repair_actions")
    return errors


def _completion_reset_errors(completion: Path, prefix: str) -> list[str]:
    marker, error = read_optional_json(completion)
    if error:
        return [error]
    errors: list[str] = []
    marker_status = str(marker.get("status") or "").strip().lower()
    if marker_status != "recheck_required":
        errors.append(f"{prefix} completion status must be recheck_required after revision")
    if marker.get("expected_artifacts_checked") is not False:
        errors.append(f"{prefix} completion expected_artifacts_checked must be false after revision")
    return errors


def longform_audit_file_gate_errors(root: Path, *, require_clean: bool = False) -> list[str]:
    json_path = root / "reviews" / "longform" / "longform_audit.json"
    report_path = json_path.with_suffix(".md")
    graph_path = root / "plot" / "longform_graph.json"
    errors = [
        f"longform audit artifact missing: {_rel(path, root)}"
        for path in (json_path, report_path, graph_path)
        if not path.exists()
    ]
    payload, error = read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    errors.extend(longform_audit_gate_errors(root, payload, require_clean=require_clean))
    return errors


def committee_review_gate_errors(root: Path, *, require_approve: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "committee_project-final-audit.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"committee review sidecar is incomplete: {state.get('message')}")
    errors.extend(f"committee review artifact missing: {_rel(path, root)}" for path in (json_path, report_path) if not path.exists())
    payload, error = read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "committee_review.v1")
    errors.extend(f"committee_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    errors.extend(_committee_decision_errors(root, payload, require_approve=require_approve))
    return errors


def _committee_decision_errors(
    root: Path,
    payload: dict[str, object],
    *,
    require_approve: bool,
) -> list[str]:
    recommendation = str(payload.get("final_recommendation") or "").strip().lower()
    errors = longform_audit_file_gate_errors(root, require_clean=True) if recommendation == "approve" else []
    errors.extend(
        f"committee review {issue.selector}: {issue.message}"
        for issue in project_review_repair_target_issues(
            root,
            payload,
            ("action_items", "disagreements"),
        )
    )
    if not require_approve:
        return errors
    action_items = payload.get("action_items") if isinstance(payload.get("action_items"), list) else []
    disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
    if recommendation != "approve":
        errors.append(f"committee final_recommendation must be approve; got {recommendation or 'missing'}")
    if action_items:
        errors.append(f"committee action_items must be empty before export/release; got {len(action_items)}")
    if disagreements:
        errors.append(f"committee disagreements must be empty before export/release; got {len(disagreements)}")
    return errors
