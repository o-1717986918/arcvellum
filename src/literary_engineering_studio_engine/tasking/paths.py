"""Shared storage and identity helpers for formal task packages.

This module intentionally owns no route selection, literary gate, or Studio
runtime behavior.  It gives lifecycle code and route definitions one stable
place for task paths, JSON parsing, and append-only workflow events.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
SUBMISSION_SCHEMA = "literary-engineering-workbench/agent-submission/v1"
EVENT_SCHEMA = "literary-engineering-workbench/workflow-event/v1"


def task_json_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.task.json"


def task_markdown_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"


def submission_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.submission.json"


def events_path(root: Path) -> Path:
    return root / "workflow" / "events" / "task_events.jsonl"


def task_id(route: str, scene_id: str, current_state: str) -> str:
    return slug(f"{route}__{scene_id}__{current_state}")


def slug(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "task"


def resolve_project_path(root: Path, value: Path | str) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    return path if path.is_absolute() else root / path


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def normalize_relative_path(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def load_task(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"task not found: {path}")
    payload = read_json(path)
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"not an agent task registry file: {path}")
    return payload


def append_event(root: Path, event_type: str, task_id_value: str, data: dict[str, object]) -> None:
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": EVENT_SCHEMA,
        "event_type": event_type,
        "task_id": task_id_value,
        "created_at": now(),
        "data": data,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
            payload = {"schema": EVENT_SCHEMA, "event_type": "invalid", "task_id": "", "created_at": "", "data": {"raw": line}}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def render_events_markdown(events: list[dict[str, object]]) -> str:
    lines = [
        "# Workflow Events",
        "",
        f"- events: {len(events)}",
        "",
        "| 时间 | 事件 | task_id | 数据 |",
        "| --- | --- | --- | --- |",
    ]
    for event in events:
        data = json.dumps(event.get("data") or {}, ensure_ascii=False)
        lines.append(f"| {event.get('created_at', '')} | {event.get('event_type', '')} | {event.get('task_id', '')} | `{data}` |")
    return "\n".join(lines).rstrip() + "\n"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
