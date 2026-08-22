"""Formal lifecycle transition for obsolete active task packages."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import append_event, now, read_json


def supersede_active_tasks(
    root: Path,
    *,
    route: str,
    scope_id: str | None,
    superseded_by: str,
    reason: str,
    exclude_task_id: str = "",
) -> int:
    """Close obsolete route tasks while preserving files and event history."""

    task_dir = root / "workflow" / "tasks"
    if not task_dir.is_dir():
        return 0
    count = 0
    for path in sorted(task_dir.glob("*.task.json")):
        payload = read_json(path)
        task_id = str(payload.get("task_id") or path.name.removesuffix(".task.json"))
        if not _eligible_task(payload, task_id, route, scope_id, exclude_task_id):
            continue
        payload.update(
            status="superseded",
            superseded_at=now(),
            superseded_by=superseded_by,
            supersession_reason=reason,
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        append_event(
            root,
            "task_superseded",
            task_id,
            {"superseded_by": superseded_by, "reason": reason},
        )
        count += 1
    return count


def _eligible_task(
    payload: dict[str, object],
    task_id: str,
    route: str,
    scope_id: str | None,
    exclude_task_id: str,
) -> bool:
    if task_id == exclude_task_id or str(payload.get("route") or "") != route:
        return False
    if str(payload.get("execution_policy") or "") == "human-required":
        return False
    if str(payload.get("status") or "") not in {"issued", "opened", "blocked"}:
        return False
    if scope_id is None:
        return True
    task_scope = str(
        payload.get("scene_id")
        or payload.get("target_id")
        or payload.get("chapter_id")
        or ""
    )
    return task_scope == scope_id


__all__ = ["supersede_active_tasks"]
