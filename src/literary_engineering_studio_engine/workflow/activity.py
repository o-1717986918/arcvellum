"""Frontend read models for visible platform-agent task activity."""

from __future__ import annotations

from pathlib import Path

from .activity_labels import EVENT_LABELS, ROUTE_LABELS, ROUTE_ORDER, STAGE_LABELS
from .activity_labels import elapsed_seconds as _elapsed_seconds
from .activity_labels import event_summary as _event_summary
from .activity_labels import friendly_step as _friendly_step
from .activity_labels import friendly_target as _friendly_target
from .activity_labels import headline as _headline
from .activity_labels import is_stale as _is_stale
from .activity_labels import progress_steps as _progress_steps
from .activity_labels import ready_task as _ready_task
from .activity_labels import route_label as _route_label
from .activity_labels import stage_priority as _stage_priority
from .activity_labels import task_purpose as _task_purpose
from .activity_labels import task_suggestion as _task_suggestion
from .activity_projection import active_from_action as _active_from_action
from .activity_projection import active_from_choice as _active_from_choice
from .activity_projection import active_from_task as _active_from_task
from .activity_projection import route_lanes as _route_lanes
from .activity_projection import select_active_task as _select_active_task
from .activity_projection import task_summary as _task_summary
from .activity_projection import timeline_entry as _timeline_entry
from .activity_sources import dashboard_actions as _dashboard_actions
from .activity_sources import last_event_by_task as _last_event_by_task
from .activity_sources import latest_open_task_by_route as _latest_open_task_by_route
from .activity_sources import load_tasks as _load_tasks
from .activity_sources import now as _now
from .activity_sources import read_events as _read_events
from .activity_sources import read_json as _read_json
from .activity_sources import relative_path as _rel
from .activity_sources import safe_current_choices as _safe_current_choices
from .activity_sources import safe_task_id as _safe_task_id
from .activity_sources import submitted_at as _submitted_at
from .dashboard_projection import project_workflow_dashboard


WORKFLOW_ACTIVITY_SCHEMA = "literary-engineering-workbench/workflow-activity/v0.1"
TASK_PACKAGE_SCHEMA = "literary-engineering-workbench/task-package-summary/v0.1"


def build_workflow_activity(project_root: Path, *, limit: int = 30) -> dict[str, object]:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    dashboard = project_workflow_dashboard(root)
    events = _read_events(root / "workflow" / "events" / "task_events.jsonl")
    tasks = _load_tasks(root)
    choices_payload = _safe_current_choices(root)
    choices = choices_payload.get("choices") if isinstance(choices_payload.get("choices"), list) else []
    active_task = _select_active_task(root, dashboard, tasks, events, choices)
    if active_task.get("task_id") and active_task.get("task_path"):
        active_task["package_summary"] = _package_hint(root, str(active_task["task_id"]))
    timeline = [_timeline_entry(root, event, tasks) for event in events[-max(1, limit) :]]
    lanes = _route_lanes(dashboard, active_task, tasks, choices)
    return {
        "schema": WORKFLOW_ACTIVITY_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "summary": {
            "active_stage": active_task.get("stage", "ready"),
            "active_route": active_task.get("route", ""),
            "waiting_for": active_task.get("waiting_for", "none"),
            "route_count": len(lanes),
            "waiting_choice_count": len(choices),
            "timeline_count": len(timeline),
        },
        "active_task": active_task,
        "route_lanes": lanes,
        "timeline": timeline,
        "waiting_choices": choices[:20],
        "dashboard": "workflow/dashboard/workflow_dashboard.json",
        "rules": [
            "This activity cockpit is read-only and must not be used as task completion proof.",
            "Only task-complete or route-audit pass can prove formal completion.",
            "Frontend highlights are derived from CLI task events, task files, human choices, and route gates.",
        ],
    }


def build_task_package_summary(project_root: Path, task_id: str) -> dict[str, object]:
    root = project_root.resolve()
    task_id = _safe_task_id(task_id)
    task_path = root / "workflow" / "tasks" / f"{task_id}.task.json"
    if not task_path.exists():
        raise FileNotFoundError(f"task package not found: {task_id}")
    task = _read_json(task_path)
    markdown_path = root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"
    markdown = markdown_path.read_text(encoding="utf-8", errors="ignore") if markdown_path.exists() else ""
    return {
        "schema": TASK_PACKAGE_SCHEMA,
        "project_root": str(root),
        "task_id": task_id,
        "task": _task_summary(root, task, task_path),
        "sections": _task_sections(task),
        "raw_evidence": {
            "task_json": _rel(task_path, root),
            "task_markdown": _rel(markdown_path, root) if markdown_path.exists() else "",
            "markdown_excerpt": markdown[:6000],
        },
        "rules": [
            "Read this package as the current executable task instruction.",
            "Writing files manually is not enough; task-submit and task-complete must still succeed.",
        ],
    }


def _task_sections(task: dict[str, object]) -> dict[str, object]:
    return {
        "purpose": _task_purpose(task),
        "required_reading": _string_items(task, "required_reading"),
        "source_paths": _string_items(task, "source_paths"),
        "expected_outputs": _string_items(task, "expected_outputs"),
        "hard_constraints": _string_items(task, "hard_constraints"),
        "validation_gates": _string_items(task, "validation_gates"),
        "forbidden_shortcuts": _string_items(task, "forbidden_shortcuts"),
        "command": str(task.get("command") or ""),
        "submission_command": str(task.get("submission_command") or ""),
        "completion_command": str(task.get("completion_command") or ""),
    }


def _string_items(task: dict[str, object], key: str) -> list[str]:
    value = task.get(key)
    return [str(item) for item in value] if isinstance(value, list) else []


def _package_hint(root: Path, task_id: str) -> dict[str, object]:
    try:
        return build_task_package_summary(root, task_id)["task"]
    except (FileNotFoundError, ValueError):
        return {}


__all__ = ["build_task_package_summary", "build_workflow_activity"]
