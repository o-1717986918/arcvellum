"""Derived state for the longform-planning route."""
from __future__ import annotations

from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..longform_materializer import longform_materialization_status
from ..story_architecture import (
    candidate_path,
    review_path,
    story_architecture_review_status,
    story_architecture_task_status,
)
from .state_common import _file_step, _longform_review_step, _read_json, _rel
def _longform_state(root: Path) -> dict[str, object]:
    steps = [
        _story_architecture_prepare_step(root),
        _story_architecture_step(root, review=False),
        _story_architecture_review_prepare_step(root),
        _story_architecture_step(root, review=True),
        _story_architecture_revision_step(root),
        _word_budget_file_step(root),
        _longform_task_step(
            "budget-agent-task",
            root,
            root / "plot" / "word_budget" / "word_budget.agent_tasks.md",
            [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"],
            "complete word_budget.agent_tasks.md, budgeted outline candidate, and budget review",
        ),
        _longform_review_step(
            "budget-review",
            root / "reviews" / "word_budget" / "word_budget_review.md",
            "write a clean word-budget review with conclusion: pass",
        ),
        _longform_task_step(
            "scene-inventory-agent-task",
            root,
            root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md",
            [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"],
            "complete scene_inventory_expansion.agent_tasks.md, scene inventory candidate, and review",
        ),
        _longform_review_step(
            "scene-inventory-review",
            root / "reviews" / "word_budget" / "scene_inventory_review.md",
            "write a clean scene inventory review with conclusion: pass",
        ),
        _longform_task_step(
            "chapter-obligation-agent-task",
            root,
            root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md",
            [root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"],
            "complete chapter_obligations.agent_tasks.md and write per-chapter reader contracts",
        ),
        _longform_review_step(
            "chapter-obligation-review",
            root / "reviews" / "word_budget" / "chapter_obligation_review.md",
            "write a clean chapter obligation review with conclusion: pass",
        ),
        _longform_materialization_step(root),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": "longform",
        "scene_id": "longform",
        "scene": "project.yaml",
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _story_architecture_prepare_step(root: Path) -> dict[str, object]:
    path = root / "plot" / "story_architecture.agent_tasks.md"
    return _file_step(
        "story-architecture-prepare",
        path,
        "run prepare-story-architecture to create the formal candidate task",
    )


def _story_architecture_review_prepare_step(root: Path) -> dict[str, object]:
    path = root / "reviews" / "longform" / "story_architecture_review.agent_tasks.md"
    candidate = candidate_path(root)
    review = review_path(root)
    current = (
        candidate.is_file()
        and review.is_file()
        and str(_read_json(review).get("candidate_sha256") or "") == _sha256(candidate)
    )
    if not current:
        return {
            "key": "story-architecture-review-prepare",
            "status": "missing",
            "path": _rel(path, root),
            "message": "story architecture review must be prepared for the exact current candidate",
            "next_action": "run prepare-story-architecture-review for the current candidate digest",
        }
    return _file_step(
        "story-architecture-review-prepare",
        path,
        "run prepare-story-architecture-review after the architecture candidate is complete",
    )


def _story_architecture_step(root: Path, *, review: bool) -> dict[str, object]:
    passed, message = story_architecture_task_status(root, review=review)
    return {
        "key": "story-architecture-review" if review else "story-architecture-agent-task",
        "status": "pass" if passed else "blocked",
        "path": "reviews/longform/story_architecture_review.json" if review else "plot/story_architecture.candidate.json",
        "message": message,
        "next_action": "" if passed else (
            "complete the independent story architecture review using a different reviewer session"
            if review
            else "complete the story architecture candidate and its platform-agent sidecar"
        ),
    }


def _story_architecture_revision_step(root: Path) -> dict[str, object]:
    complete, message, verdict = story_architecture_review_status(root)
    if not complete:
        return {
            "key": "story-architecture-revision",
            "status": "blocked",
            "path": "plot/story_architecture.candidate.json",
            "message": message,
            "next_action": "complete the exact-candidate architecture review before revision",
        }
    if verdict == "pass":
        return {
            "key": "story-architecture-revision",
            "status": "pass",
            "path": "plot/story_architecture.candidate.json",
            "message": "story architecture requires no revision",
            "next_action": "",
        }
    if verdict == "block":
        return {
            "key": "story-architecture-revision",
            "status": "blocked",
            "path": "reviews/longform/story_architecture_review.json",
            "message": "story architecture review blocked further planning",
            "next_action": "resolve the blocking architecture decision with the user",
        }
    return {
        "key": "story-architecture-revision",
        "status": "blocked",
        "path": "plot/story_architecture.candidate.json",
        "message": "story architecture review requires a writer revision",
        "next_action": "revise the exact architecture candidate against every required change",
    }


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _word_budget_file_step(root: Path) -> dict[str, object]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    required = [json_path, markdown_path, budget_task, scene_task, obligation_task]
    missing = [_rel(path, root) for path in required if not path.exists()]
    if missing:
        return {
            "key": "word-budget-file",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing " + ", ".join(missing),
            "next_action": "run word-budget / longform-budget to create budget JSON, report, scene-inventory sidecar, and chapter-obligation sidecar",
        }
    payload = _read_json(json_path)
    if not payload or payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        return {
            "key": "word-budget-file",
            "status": "invalid",
            "path": _rel(json_path, root),
            "message": "word_budget.json is invalid or has wrong schema",
            "next_action": "rerun word-budget / longform-budget",
        }
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    return {
        "key": "word-budget-file",
        "status": "pass",
        "path": _rel(json_path, root),
        "message": f"word budget exists; status={payload.get('status', '')}",
        "target_words": totals.get("target_words", 0),
        "chapter_count": totals.get("chapter_count", 0),
        "scene_count": totals.get("scene_count", 0),
        "next_action": "",
    }


def _longform_materialization_step(root: Path) -> dict[str, object]:
    passed, message = longform_materialization_status(root)
    return {
        "key": "planning-materialization",
        "status": "pass" if passed else "missing",
        "path": "workflow/longform_materialization.json",
        "message": message,
        "next_action": "" if passed else "materialize the reviewed longform plan, safely adopting matching existing formal contracts without overwriting them",
    }

def _longform_task_step(key: str, root: Path, path: Path, required_outputs: list[Path], next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    missing = [_rel(item, root) for item in required_outputs if not item.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else next_action,
    }
