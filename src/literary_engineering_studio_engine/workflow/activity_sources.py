"""Read-only task, event, submission, and choice sources for activity views."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ..project_interaction import build_current_human_choices


def load_tasks(root: Path) -> dict[str, dict[str, object]]:
    task_dir = root / "workflow" / "tasks"
    if not task_dir.exists():
        return {}
    tasks: dict[str, dict[str, object]] = {}
    for path in sorted(task_dir.glob("*.task.json")):
        payload = read_json(path)
        task_id = str(payload.get("task_id") or path.name.removesuffix(".task.json"))
        if not task_id:
            continue
        payload["_path"] = relative_path(path, root)
        tasks[task_id] = payload
    return tasks


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {"event_type": "invalid", "task_id": "", "created_at": "", "data": {"raw": line}}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_current_choices(root: Path) -> dict[str, object]:
    try:
        return build_current_human_choices(root)
    except (RuntimeError, ValueError, FileNotFoundError):
        return {"choices": [], "recent_choices": []}


def dashboard_actions(dashboard: dict[str, object]) -> list[dict[str, object]]:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    return [item for item in actions if isinstance(item, dict)]


def last_event_by_task(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for event in events:
        task_id = str(event.get("task_id") or "")
        if task_id:
            latest[task_id] = event
    return latest


def latest_open_task_by_route(tasks: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for task_id, task in tasks.items():
        route = str(task.get("route") or "")
        if not route:
            continue
        current = result.get(route)
        sort_value = str(task.get("opened_at") or task.get("task_id") or task_id)
        current_value = str(current.get("opened_at") or current.get("task_id") or "") if current else ""
        if current is None or sort_value >= current_value:
            copy = dict(task)
            copy["task_id"] = task_id
            result[route] = copy
    return result


def submitted_at(root: Path, task_id: str) -> str:
    path = root / "workflow" / "tasks" / f"{task_id}.submission.json"
    return str(read_json(path).get("submitted_at") or "")


def safe_task_id(value: str) -> str:
    task_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.\-\u4e00-\u9fff]{1,200}", task_id) or ".." in task_id:
        raise ValueError("invalid task_id")
    return task_id


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
