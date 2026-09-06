"""Resolve the formal task identity that authored a planning candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from literary_engineering_studio_engine.tasking.agent_tasks.writer import agent_task_completion_status
from ...tasking.storage import load_task_payload


class PlanningReviewSpec(Protocol):
    kind: str
    candidate: str
    author_task: str
    author_states: tuple[str, ...]


def candidate_writer_identity(root: Path, spec: PlanningReviewSpec) -> str:
    task_path = candidate_writer_task_path(root, spec)
    if task_path:
        payload = load_task_payload(root.resolve() / task_path)
        identifier = str(payload.get("task_id") or Path(task_path).stem)
        return f"studio:writer:{identifier}"
    marker = agent_task_completion_status(root.resolve() / spec.author_task, root=root.resolve())
    if marker.get("complete") is True:
        digest = str(marker.get("task_digest") or "")[:16]
        return f"sidecar:writer:{spec.kind}:{digest}"
    return ""


def candidate_writer_task_path(root: Path, spec: PlanningReviewSpec) -> str:
    completed: list[tuple[str, str]] = []
    project = root.resolve()
    for path in (project / "workflow" / "tasks").glob("*.task.json"):
        try:
            payload = load_task_payload(path)
        except (OSError, ValueError):
            continue
        outputs = [str(item).replace("\\", "/") for item in payload.get("expected_outputs") or []]
        if (
            payload.get("status") == "complete"
            and str(payload.get("current_state") or "") in spec.author_states
            and spec.candidate in outputs
        ):
            completed.append(
                (str(payload.get("completed_at") or ""), path.relative_to(project).as_posix())
            )
    return max(completed)[1] if completed else ""


__all__ = ["candidate_writer_identity", "candidate_writer_task_path"]
