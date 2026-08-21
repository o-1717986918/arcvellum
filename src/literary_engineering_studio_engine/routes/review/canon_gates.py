"""Canon candidate, approval, apply, lint, and semantic review Gates."""

from __future__ import annotations

from pathlib import Path

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path
from .evidence import (
    approval_matches_file,
    approval_record_for_run,
    read_optional_json,
    to_int,
)


def canon_patch_path_for_task(root: Path, task: dict[str, object]) -> Path:
    patch = str(task.get("patch") or "").strip()
    if patch:
        return _resolve_project_path(root, patch)
    for value in [*task.get("expected_outputs", []), *task.get("source_paths", [])]:
        relative = str(value).replace("\\", "/")
        if relative.startswith("canon/patches/") and relative.endswith("_canon_patch.json"):
            return _resolve_project_path(root, relative)
    return root / "canon" / "patches" / "missing_canon_patch.json"


def canon_patch_candidate_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = canon_patch_path_for_task(root, task)
    payload, error = read_optional_json(patch)
    if error:
        return [error]
    errors = _canon_patch_header_errors(payload)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        errors.append("canon patch must contain at least one durable fact item")
    for index, item in enumerate(items):
        errors.extend(_canon_patch_item_errors(item, index))
    completion = agent_task_completion_status(patch.with_suffix(".agent_tasks.md"), root=root)
    if completion.get("complete") is not True:
        errors.append(f"canon-evolve sidecar is incomplete: {completion.get('message')}")
    report = patch.with_suffix(".md")
    if not report.is_file():
        errors.append(f"canon patch report missing: {_rel(report, root)}")
    return errors


def _canon_patch_header_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-candidate/v0.1":
        errors.append("canon patch has wrong or missing schema")
    if payload.get("canon_change") is not True:
        errors.append("canon patch must declare canon_change=true before project-level approval")
    status = str(payload.get("status") or "").strip().lower()
    if payload.get("applied") is True or status == "applied":
        errors.append("canon patch revision/approval task must not mark the candidate applied")
    return errors


def _canon_patch_item_errors(item: object, index: int) -> list[str]:
    if not isinstance(item, dict):
        return [f"canon patch item {index + 1} must be an object"]
    errors: list[str] = []
    required = ("type", "summary", "source_evidence", "target_files", "risk_level", "requires_user_approval")
    missing = [
        field
        for field in required
        if field not in item or item.get(field) is None or item.get(field) == "" or item.get(field) == []
    ]
    if missing:
        errors.append(f"canon patch item {index + 1} missing fields: {', '.join(missing)}")
    targets = item.get("target_files") if isinstance(item.get("target_files"), list) else []
    for target in targets:
        value = str(target).replace("\\", "/")
        if Path(value).is_absolute() or ".." in Path(value).parts or not value.startswith("canon/"):
            errors.append(f"canon patch item {index + 1} has unsafe target_file: {value}")
    return errors


def canon_patch_decision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    require_approve: bool,
) -> list[str]:
    patch = canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    approval = approval_record_for_run(root, patch_id)
    decision = str(approval.get("decision") or "").strip().lower()
    allowed = {"approve"} if require_approve else {"approve", "revise", "reject", "defer"}
    if decision not in allowed:
        return [f"canon patch decision for {patch_id} must be one of {sorted(allowed)}; got {decision or 'missing'}"]
    if not approval_matches_file(approval, patch):
        return [f"canon patch decision for {patch_id} is stale or not bound to the current candidate"]
    return []


def canon_patch_apply_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    apply_manifest = root / "canon" / "applied" / f"{patch_id}_apply.json"
    payload, error = read_optional_json(apply_manifest)
    if error:
        return [error]
    errors = _canon_apply_manifest_errors(payload)
    errors.extend(_canon_apply_patch_evidence_errors(root, patch, apply_manifest))
    return errors


def _canon_apply_manifest_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-apply/v0.1":
        errors.append("canon apply manifest has wrong or missing schema")
    if payload.get("status") != "applied":
        errors.append(f"canon apply status must be applied; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved") is True:
        errors.append("canon apply used allow_unapproved")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    candidate_sha256 = str(payload.get("candidate_sha256") or "").strip().lower()
    if approval.get("decision") != "approve":
        errors.append("canon apply manifest must carry an approve record")
    if not candidate_sha256 or str(approval.get("subject_sha256") or "").strip().lower() != candidate_sha256:
        errors.append("canon apply approval digest does not match the pre-apply patch candidate")
    return errors


def _canon_apply_patch_evidence_errors(root: Path, patch: Path, apply_manifest: Path) -> list[str]:
    errors: list[str] = []
    patch_payload, patch_error = read_optional_json(patch)
    if patch_error:
        errors.append(patch_error)
    elif patch_payload.get("applied") is not True or patch_payload.get("apply_manifest") != _rel(apply_manifest, root):
        errors.append("canon patch does not point to its applied manifest")
    if not (root / "canon" / "canon_change_log.md").is_file():
        errors.append("canon change log is missing after apply")
    return errors


def canon_lint_gate_errors(root: Path, *, require_clean: bool = False) -> list[str]:
    json_path = root / "reviews" / "canon_lint.json"
    report_path = root / "reviews" / "canon_lint.md"
    errors = [f"canon-lint artifact missing: {_rel(path, root)}" for path in (report_path, json_path) if not path.exists()]
    payload, error = read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/canon-lint/v0.1":
        errors.append("canon_lint.json has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocking = to_int(summary.get("blocking_count"))
    warnings = to_int(summary.get("warning_count"))
    status = str(payload.get("status") or "").strip().lower()
    if blocking:
        errors.append(f"canon-lint blocking_count must be 0; got {blocking}")
    if require_clean and warnings:
        errors.append(f"canon-lint warning_count must be 0 after project repair; got {warnings}")
    allowed_statuses = {"pass"} if require_clean else {"pass", "pass_with_warnings"}
    if status not in allowed_statuses:
        expected = "pass" if require_clean else "pass/pass_with_warnings"
        errors.append(f"canon-lint status must be {expected}; got {status or 'missing'}")
    return errors


def canon_review_gate_errors(root: Path, *, require_pass: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "canon_review.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"canon review sidecar is incomplete: {state.get('message')}")
    errors.extend(f"canon review artifact missing: {_rel(path, root)}" for path in (json_path, report_path) if not path.exists())
    payload, error = read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "canon_review.v1")
    errors.extend(f"canon_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    if require_pass:
        errors.extend(_canon_review_cleanliness_errors(payload))
    return errors


def _canon_review_cleanliness_errors(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    findings = {
        "blocking_issues": payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else [],
        "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        "unresolved_facts": payload.get("unresolved_facts") if isinstance(payload.get("unresolved_facts"), list) else [],
        "timeline_risks": payload.get("timeline_risks") if isinstance(payload.get("timeline_risks"), list) else [],
    }
    if conclusion != "pass":
        errors.append(f"canon review conclusion must be pass; got {conclusion or 'missing'}")
    labels = {
        "blocking_issues": "canon review blocking_issues must be empty",
        "warnings": "canon review warnings must be resolved before export/release",
        "unresolved_facts": "canon review unresolved_facts must be empty",
        "timeline_risks": "canon review timeline_risks must be empty",
    }
    for field, items in findings.items():
        if items:
            errors.append(f"{labels[field]}; got {len(items)}")
    return errors
