"""Formal Gate validation for longform-planning tasks."""

from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...longform_materializer import longform_materialization_status
from ...story_architecture import (
    story_architecture_status,
    story_architecture_task_status,
)
from ...task_paths import relative_path, resolve_project_path
from .support import file_sha256, read_optional_json, static_review_conclusion, to_int


_PLANNING_STATES = {
    "word-budget-file",
    "budget-agent-task",
    "budget-review",
    "scene-inventory-agent-task",
    "scene-inventory-review",
    "chapter-obligation-agent-task",
    "chapter-obligation-review",
    "planning-materialization",
}

_SUCCESS_NOTES = {
    "budget-agent-task": "word-budget expansion reviewed",
    "budget-review": "word-budget expansion reviewed",
    "scene-inventory-agent-task": "scene inventory reviewed",
    "scene-inventory-review": "scene inventory reviewed",
    "chapter-obligation-agent-task": "chapter obligation reviewed",
    "chapter-obligation-review": "chapter obligation reviewed",
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
    if current_state in {"budget-agent-task", "budget-review"}:
        _validate_candidate_review(
            root, task, current_state, errors,
            task_path=root / "plot" / "word_budget" / "word_budget.agent_tasks.md",
            candidate=root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md",
            review=root / "reviews" / "word_budget" / "word_budget_review.md",
            planning_label="word-budget expansion",
            review_label="word-budget review",
            revision_label="word-budget revision",
        )
    elif current_state in {"scene-inventory-agent-task", "scene-inventory-review"}:
        _validate_candidate_review(
            root, task, current_state, errors,
            task_path=root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md",
            candidate=root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md",
            review=root / "reviews" / "word_budget" / "scene_inventory_review.md",
            planning_label="scene-inventory expansion",
            review_label="scene-inventory review",
            revision_label="scene-inventory revision",
        )
    elif current_state in {"chapter-obligation-agent-task", "chapter-obligation-review"}:
        _validate_candidate_review(
            root, task, current_state, errors,
            task_path=root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md",
            candidate=root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md",
            review=root / "reviews" / "word_budget" / "chapter_obligation_review.md",
            planning_label="chapter obligation planning",
            review_label="chapter obligation review",
            revision_label="chapter-obligation revision",
        )
    if current_state == "planning-materialization":
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


def _validate_candidate_review(
    root: Path,
    task: dict[str, object],
    current_state: str,
    errors: list[str],
    *,
    task_path: Path,
    candidate: Path,
    review: Path,
    planning_label: str,
    review_label: str,
    revision_label: str,
) -> None:
    errors.extend(word_budget_file_gate_errors(root))
    errors.extend(_sidecar_completion_errors(task_path, root, planning_label))
    errors.extend(_required_artifact_errors(root, [candidate], planning_label))
    revision_state = current_state.endswith("-review")
    errors.extend(_review_gate_errors(review, root, review_label, require_pass=revision_state))
    if revision_state:
        errors.extend(repair_targets_changed(root, task, revision_label))


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


def _sidecar_completion_errors(task_path: Path, root: Path, label: str) -> list[str]:
    state = agent_task_completion_status(task_path, root=root)
    return [] if state.get("complete") is True else [f"{label} sidecar is incomplete: {state.get('message')}"]


def _required_artifact_errors(root: Path, paths: list[Path], label: str) -> list[str]:
    missing = [relative_path(path, root) for path in paths if not path.exists()]
    return [] if not missing else [f"{label} required artifact missing: {', '.join(missing)}"]


def _review_gate_errors(path: Path, root: Path, label: str, *, require_pass: bool = True) -> list[str]:
    conclusion = static_review_conclusion(path)
    allowed = {"pass", "pass_with_notes", "revise_required", "reject"}
    if conclusion not in allowed:
        return [f"{label} conclusion must be recorded; got {conclusion or 'missing'} at {relative_path(path, root)}"]
    return [] if not require_pass or conclusion == "pass" else [f"{label} conclusion must be pass; got {conclusion or 'missing'} at {relative_path(path, root)}"]
