"""Deterministic state dispatch for the project review route."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...task_paths import relative_path as _rel
from .canon_gates import (
    canon_lint_gate_errors,
    canon_patch_apply_gate_errors,
    canon_patch_candidate_gate_errors,
    canon_patch_decision_gate_errors,
    canon_review_gate_errors,
)
from .evidence import declared_repair_targets_changed
from .project_gates import (
    committee_review_gate_errors,
    longform_audit_file_gate_errors,
    project_review_revision_gate_errors,
)


GateValidator = Callable[[Path, dict[str, object]], list[str]]


SUCCESS_NOTES = {
    "canon-patch-revision": "canon patch candidate revised; fresh content-bound approval is required",
    "canon-patch-approval": "canon patch decision recorded against the current candidate",
    "canon-patch-apply": "approved canon patch applied to durable ledger",
    "canon-review-agent-task": "canon review verdict recorded; clean pass or formal revision routing may continue",
    "canon-review-pass": "canon repair completed; deterministic lint refreshed and review evidence reset",
    "committee-agent-task": "committee verdict recorded; approval or formal revision routing may continue",
    "committee-pass": "committee repair completed; project audits refreshed and review evidence reset",
}


def review_audit_state_gate_validation(
    root: Path,
    task: dict[str, object],
) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    validator = GATE_VALIDATORS.get(current_state)
    errors = validator(root, task) if validator else []
    note = SUCCESS_NOTES.get(current_state)
    return errors, [note] if note and not errors else []


def _canon_patch_revision(root: Path, task: dict[str, object]) -> list[str]:
    errors = declared_repair_targets_changed(root, task, "canon-patch revision")
    errors.extend(canon_patch_candidate_gate_errors(root, task))
    return errors


def _canon_patch_approval(root: Path, task: dict[str, object]) -> list[str]:
    errors = canon_patch_candidate_gate_errors(root, task)
    errors.extend(canon_patch_decision_gate_errors(root, task, require_approve=False))
    return errors


def _canon_patch_deferred(_root: Path, _task: dict[str, object]) -> list[str]:
    return ["canon patch is intentionally deferred; resume it through an explicit new decision"]


def _canon_patch_apply(root: Path, task: dict[str, object]) -> list[str]:
    return canon_patch_apply_gate_errors(root, task)


def _canon_lint(root: Path, _task: dict[str, object]) -> list[str]:
    return canon_lint_gate_errors(root)


def _canon_review_prepare(root: Path, _task: dict[str, object]) -> list[str]:
    errors = canon_lint_gate_errors(root)
    task_path = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
    if not task_path.exists():
        errors.append(f"canon review sidecar missing: {_rel(task_path, root)}")
    return errors


def _canon_review_execute(root: Path, _task: dict[str, object]) -> list[str]:
    errors = canon_lint_gate_errors(root)
    errors.extend(canon_review_gate_errors(root, require_pass=False))
    return errors


def _canon_review_revise(root: Path, task: dict[str, object]) -> list[str]:
    return project_review_revision_gate_errors(root, task, review_kind="canon")


def _longform_audit(root: Path, _task: dict[str, object]) -> list[str]:
    errors = canon_review_gate_errors(root, require_pass=True)
    errors.extend(longform_audit_file_gate_errors(root))
    return errors


def _committee_prepare(root: Path, _task: dict[str, object]) -> list[str]:
    errors = canon_review_gate_errors(root, require_pass=True)
    errors.extend(longform_audit_file_gate_errors(root))
    task_path = root / "reviews" / "agent" / "committee_project-final-audit.agent_tasks.md"
    if not task_path.exists():
        errors.append(f"committee sidecar missing: {_rel(task_path, root)}")
    return errors


def _committee_execute(root: Path, _task: dict[str, object]) -> list[str]:
    errors = canon_review_gate_errors(root, require_pass=True)
    errors.extend(longform_audit_file_gate_errors(root))
    errors.extend(committee_review_gate_errors(root, require_approve=False))
    return errors


def _committee_revise(root: Path, task: dict[str, object]) -> list[str]:
    return project_review_revision_gate_errors(root, task, review_kind="committee")


GATE_VALIDATORS: dict[str, GateValidator] = {
    "canon-patch-revision": _canon_patch_revision,
    "canon-patch-approval": _canon_patch_approval,
    "canon-patch-deferred": _canon_patch_deferred,
    "canon-patch-apply": _canon_patch_apply,
    "canon-lint-file": _canon_lint,
    "canon-review-task-file": _canon_review_prepare,
    "canon-review-agent-task": _canon_review_execute,
    "canon-review-pass": _canon_review_revise,
    "longform-audit-file": _longform_audit,
    "committee-task-file": _committee_prepare,
    "committee-agent-task": _committee_execute,
    "committee-pass": _committee_revise,
}
