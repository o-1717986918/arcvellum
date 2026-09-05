"""Formal Gate validation for longform-planning tasks."""

from __future__ import annotations

from pathlib import Path

from ...longform_materializer import longform_materialization_status
from ...literary.planning.review import (
    all_planning_reviews_pass,
    planning_candidate_status,
    planning_review_prepare_status,
    planning_revision_review_status,
    planning_review_status,
    planning_review_task_status,
    review_spec,
)
from ...story_architecture import (
    story_architecture_status,
    story_architecture_task_status,
)
from ...task_paths import relative_path, resolve_project_path
from .support import file_sha256, read_optional_json, to_int


_PLANNING_STATES = {
    "word-budget-file",
    "budget-agent-task",
    "budget-review-prepare",
    "budget-review",
    "budget-revision",
    "scene-inventory-agent-task",
    "scene-inventory-review-prepare",
    "scene-inventory-review",
    "scene-inventory-revision",
    "chapter-obligation-agent-task",
    "chapter-obligation-review-prepare",
    "chapter-obligation-review",
    "chapter-obligation-revision",
    "planning-materialization",
}

_SUCCESS_NOTES = {
    "budget-agent-task": "word-budget expansion candidate completed",
    "budget-review": "word-budget expansion independently reviewed",
    "scene-inventory-agent-task": "scene inventory candidate completed",
    "scene-inventory-review": "scene inventory independently reviewed",
    "chapter-obligation-agent-task": "chapter obligation candidate completed",
    "chapter-obligation-review": "chapter obligation plan independently reviewed",
}


def validate_task(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors = _story_architecture_gate_errors(root, task, current_state)
    errors.extend(_planning_architecture_errors(root, current_state))
    errors.extend(_planning_state_errors(root, task, current_state))
    notes = _success_notes(root, current_state, errors)
    return errors, notes


def _planning_architecture_errors(root: Path, current_state: str) -> list[str]:
    if current_state not in _PLANNING_STATES:
        return []
    passed, message, _payload = story_architecture_status(root, require_review=True)
    return [] if passed else ["story architecture gate: " + message]


def _planning_state_errors(
    root: Path, task: dict[str, object], current_state: str
) -> list[str]:
    errors: list[str] = []
    if current_state == "word-budget-file":
        return word_budget_file_gate_errors(root)
    planning_kind = _planning_kind(current_state)
    if planning_kind:
        errors.extend(word_budget_file_gate_errors(root))
        if current_state.endswith("agent-task"):
            passed, message = planning_candidate_status(root, planning_kind)
            if not passed:
                errors.append(message)
        elif current_state.endswith("review-prepare"):
            passed, message = planning_review_prepare_status(root, planning_kind)
            if not passed:
                errors.append(message)
        elif current_state.endswith("-review"):
            passed, message, _verdict = planning_review_task_status(root, planning_kind)
            if not passed:
                errors.append(message)
        elif current_state.endswith("-revision"):
            errors.extend(_planning_revision_errors(root, task, planning_kind))
    if current_state == "planning-materialization":
        passed, message = all_planning_reviews_pass(root)
        if not passed:
            errors.append(message)
        passed, message = longform_materialization_status(root)
        if not passed:
            errors.append(message)
    return errors
def _success_notes(root: Path, current_state: str, errors: list[str]) -> list[str]:
    if errors:
        return []
    note = _SUCCESS_NOTES.get(current_state)
    if note:
        return [note]
    if current_state == "planning-materialization":
        passed, message = longform_materialization_status(root)
        return [message] if passed else []
    return []


def _story_architecture_gate_errors(
    root: Path, task: dict[str, object], current_state: str
) -> list[str]:
    errors: list[str] = []
    if current_state == "story-architecture-prepare" and not (
        root / "plot" / "story_architecture.agent_tasks.md"
    ).is_file():
        errors.append("story architecture task sidecar is missing")
    if current_state == "story-architecture-agent-task":
        passed, message = story_architecture_task_status(root, review=False)
        if not passed:
            errors.append(message)
    if current_state == "story-architecture-review-prepare" and not (
        root / "reviews" / "longform" / "story_architecture_review.agent_tasks.md"
    ).is_file():
        errors.append("story architecture review task sidecar is missing")
    if current_state == "story-architecture-review":
        passed, message = story_architecture_task_status(root, review=True)
        if not passed:
            errors.append(message)
    if current_state == "story-architecture-revision":
        errors.extend(_story_architecture_revision_review_errors(root, task))
        errors.extend(repair_targets_changed(root, task, "story-architecture revision"))
        candidate_passed, candidate_message = story_architecture_task_status(root, review=False)
        if not candidate_passed:
            errors.append(candidate_message)
    return errors


def _planning_kind(current_state: str) -> str:
    if current_state.startswith("budget-"):
        return "budget"
    if current_state.startswith("scene-inventory-"):
        return "scene_inventory"
    if current_state.startswith("chapter-obligation-"):
        return "chapter_obligation"
    return ""


def _planning_revision_errors(
    root: Path, task: dict[str, object], kind: str
) -> list[str]:
    spec = review_spec(kind)
    hashes = task.get("repair_target_sha256_before_revision")
    before = hashes if isinstance(hashes, dict) else {}
    prior = str(before.get(spec.candidate) or "").strip().lower()
    authorized, message = planning_revision_review_status(root, kind, prior)
    if not authorized:
        return [message]
    errors = repair_targets_changed(root, task, f"{spec.label} revision")
    candidate_ok, candidate_message = planning_candidate_status(root, kind)
    if not candidate_ok:
        errors.append(candidate_message)
    return errors


def word_budget_file_gate_errors(root: Path) -> list[str]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    artifacts = (
        root / "plot" / "word_budget" / "word_budget.md",
        json_path,
        root / "plot" / "word_budget" / "word_budget.agent_tasks.md",
        root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md",
        root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md",
    )
    errors = [f"missing longform budget artifact: {relative_path(path, root)}" for path in artifacts if not path.exists()]
    payload, error = read_optional_json(json_path)
    if error:
        return [*errors, error]
    if payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        errors.append("word_budget.json has wrong or missing schema")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if to_int(target.get("target_words") or totals.get("target_words")) <= 0:
        errors.append("word_budget.json target Chinese-content characters must be positive")
    if not isinstance(payload.get("chapter_budgets"), list) or not payload.get("chapter_budgets"):
        errors.append("word_budget.json must contain chapter_budgets")
    if not isinstance(payload.get("scene_inventory_binding"), dict):
        errors.append("word_budget.json must contain scene_inventory_binding")
    return errors


def repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    hashes = task.get("repair_target_sha256_before_revision")
    before = hashes if isinstance(hashes, dict) else {}
    if not targets or not before:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = resolve_project_path(root, target)
        previous = str(before.get(target) or "").strip().lower()
        if path.is_file() and previous and file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def _story_architecture_revision_review_errors(
    root: Path, task: dict[str, object]
) -> list[str]:
    review, error = read_optional_json(
        root / "reviews" / "longform" / "story_architecture_review.json"
    )
    if error:
        return [error]
    before = task.get("repair_target_sha256_before_revision")
    prior = str(before.get("plot/story_architecture.candidate.json") or "").strip().lower() if isinstance(before, dict) else ""
    errors = _story_architecture_review_contract_errors(review, prior)
    writer = str(review.get("writer_session_id") or "").strip()
    reviewer = str(review.get("reviewer_session_id") or "").strip()
    if not writer or not reviewer or writer == reviewer:
        errors.append("story architecture revision requires an independent pre-revision review")
    return errors


def _story_architecture_review_contract_errors(
    review: dict[str, object], prior: str
) -> list[str]:
    errors: list[str] = []
    if review.get("schema") != "literary-engineering-workbench/story-architecture-review/v1":
        errors.append("story architecture revision review schema is invalid")
    candidate_digest = str(review.get("candidate_sha256") or "").strip().lower()
    if not prior or candidate_digest != prior:
        errors.append("story architecture revision review is not bound to the pre-revision candidate")
    status = str(review.get("status") or "").strip().lower()
    verdict = str(review.get("verdict") or "").strip().lower()
    if status != "complete" or verdict != "revise":
        errors.append("story architecture revision requires a completed revise verdict")
    return errors
