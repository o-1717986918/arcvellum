"""Test helpers for formal longform planning review evidence."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.agent_tasks import (
    write_agent_completion_marker,
    write_agent_tasks,
)
from literary_engineering_studio_engine.literary.planning.review import (
    prepare_longform_review,
    review_spec,
)


def complete_planning_review(root: Path, kind: str) -> None:
    """Create a digest-bound independent passing review for a test candidate."""

    spec = review_spec(kind)
    author_task = root / spec.author_task
    if not author_task.is_file():
        write_agent_tasks(
            author_task,
            title=f"{spec.label} test author task",
            root=root,
            source_paths=[root / spec.candidate],
            tasks=[("write candidate", f"Write `{spec.candidate}`.")],
        )
    write_agent_completion_marker(author_task, root=root, handled_by="test-writer")

    prepared = prepare_longform_review(root, kind)
    payload = json.loads(prepared.review_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "complete",
            "reviewer_session_id": f"test-reviewer:{spec.kind}",
            "verdict": "pass",
            "summary": f"Independent {spec.label} review passed for the test fixture.",
            "evidence_paths": [spec.candidate, "plot/word_budget/word_budget.json"],
            "findings": [],
            "required_changes": [],
        }
    )
    prepared.review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    prepared.report_path.write_text(
        f"# {spec.label} review\n\n- Verdict: pass\n",
        encoding="utf-8",
    )
    write_agent_completion_marker(
        prepared.task_path,
        root=root,
        handled_by=f"test-reviewer:{spec.kind}",
    )


def complete_all_planning_reviews(root: Path) -> None:
    for kind in ("budget", "scene_inventory", "chapter_obligation"):
        complete_planning_review(root, kind)


__all__ = ["complete_all_planning_reviews", "complete_planning_review"]
