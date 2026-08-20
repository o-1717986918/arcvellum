"""Pure projections for active work, route lanes, and task timelines."""

from __future__ import annotations

from pathlib import Path

from ..task_registry import SUPPORTED_ROUTES
from .activity_labels import (
    EVENT_LABELS,
    ROUTE_ORDER,
    STAGE_LABELS,
    elapsed_seconds,
    event_summary,
    headline,
    is_stale,
    progress_steps,
    route_label,
    stage_priority,
    task_suggestion,
)
from .activity_sources import (
    dashboard_actions,
    last_event_by_task,
    latest_open_task_by_route,
    relative_path,
    submitted_at,
)


def select_active_task(
    root: Path,
    dashboard: dict[str, object],
    tasks: dict[str, dict[str, object]],
    events: list[dict[str, object]],
    choices: list[object],
) -> dict[str, object]:
    candidates: list[tuple[int, str, dict[str, object]]] = []
    last_events = last_event_by_task(events)
    for task_id, task in tasks.items():
        candidate = active_from_task(root, task_id, task, last_events.get(task_id))
        candidates.append(_ranked(candidate))
    for choice in choices:
        if isinstance(choice, dict):
            candidates.append(_ranked(active_from_choice(choice)))
    for action in dashboard_actions(dashboard):
        candidates.append(_ranked(active_from_action(action)))
    if not candidates:
        from .activity_labels import ready_task

        return ready_task()
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _ranked(candidate: dict[str, object]) -> tuple[int, str, dict[str, object]]:
    stage = str(candidate.get("stage") or "")
    return stage_priority(stage), str(candidate.get("last_event_at") or ""), candidate


def active_from_task(
    root: Path,
    task_id: str,
    task: dict[str, object],
    last_event: dict[str, object] | None,
) -> dict[str, object]:
    status = _text_field(task, "status", "issued")
    event_type = _text_field(last_event, "event_type")
    stage, waiting_for, risk = _task_stage(root, task_id, task, status, event_type)
    current_state = _text_field(task, "current_state")
    route = _text_field(task, "route")
    scene_id = _text_field(task, "scene_id")
    task_path = root / "workflow" / "tasks" / f"{task_id}.task.json"
    markdown_path = root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"
    event_at = _last_event_at(task, last_event)
    return {
        "task_id": task_id,
        "route": route,
        "route_label": route_label(route),
        "target": scene_id or _text_field(task, "target_id"),
        "current_step": current_state,
        "task_type": _text_field(task, "task_type"),
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "waiting_for": waiting_for,
        "risk": risk,
        "headline": headline(route, scene_id, current_state, stage),
        "suggested_action": task_suggestion(stage, task, last_event),
        "last_event": event_type or status,
        "last_event_at": event_at,
        "elapsed_seconds": elapsed_seconds(event_at),
        "task_path": relative_path(task_path, root),
        "task_markdown": relative_path(markdown_path, root) if markdown_path.exists() else "",
        "expected_outputs": _string_items(task, "expected_outputs"),
        "source_paths": _string_items(task, "source_paths"),
        "progress_steps": progress_steps(route, current_state, stage),
    }


def _task_stage(
    root: Path,
    task_id: str,
    task: dict[str, object],
    status: str,
    event_type: str,
) -> tuple[str, str, str]:
    if event_type == "task_blocked" or status == "blocked":
        return "blocked", "gate", "blocking"
    if status == "opened":
        risk = "stale" if is_stale(str(task.get("opened_at") or ""), 1800) else "normal"
        return "waiting_agent", "agent", risk
    if status == "submitted":
        risk = "stale" if is_stale(submitted_at(root, task_id), 900) else "normal"
        return "waiting_gate", "gate", risk
    if status == "complete" or event_type == "task_completed":
        return "completed", "none", "done"
    return "issued", "agent", "normal"


def _last_event_at(task: dict[str, object], last_event: dict[str, object] | None) -> str:
    if last_event:
        return str(last_event.get("created_at") or task.get("opened_at") or "")
    return str(task.get("opened_at") or "")


def _text_field(payload: dict[str, object] | None, key: str, default: str = "") -> str:
    if payload is None:
        return default
    value = payload.get(key)
    return default if value is None or value == "" else str(value)


def _string_items(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    return [str(item) for item in value] if isinstance(value, list) else []


def active_from_choice(choice: dict[str, object]) -> dict[str, object]:
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    target_id = str(target.get("scene_id") or target.get("target_id") or "")
    route = str(choice.get("route") or "")
    return {
        "task_id": str(choice.get("task_id") or ""),
        "choice_id": str(choice.get("choice_id") or ""),
        "route": route,
        "route_label": route_label(route),
        "target": target_id,
        "current_step": str(choice.get("task_step") or choice.get("decision_type") or ""),
        "stage": "waiting_user",
        "stage_label": STAGE_LABELS["waiting_user"],
        "waiting_for": "user",
        "risk": "attention",
        "headline": str(choice.get("title") or "有一个节点等待你决定"),
        "suggested_action": str(choice.get("summary") or "请在前端记录你的选择，平台 Agent 后续会读取这条证据。"),
        "last_event": "human_choice_waiting",
        "last_event_at": "",
        "elapsed_seconds": 0,
        "expected_outputs": [],
        "source_paths": [str(item) for item in choice.get("source_paths") or []],
        "progress_steps": progress_steps(route, str(choice.get("task_step") or ""), "waiting_user"),
    }


def active_from_action(action: dict[str, object]) -> dict[str, object]:
    route = str(action.get("route") or "")
    current_step = str(action.get("current_step") or "")
    blocked = current_step == "route-audit" or "blocking" in str(action.get("next_action") or "").lower()
    stage = "next_action"
    return {
        "task_id": "", "route": route, "route_label": route_label(route), "target": str(action.get("target") or ""),
        "current_step": current_step, "stage": stage, "stage_label": STAGE_LABELS.get(stage, stage),
        "waiting_for": "gate" if blocked else "agent", "risk": "blocking" if blocked else "normal",
        "headline": headline(route, str(action.get("target") or ""), current_step, stage),
        "suggested_action": str(action.get("next_action") or "按正式状态机继续领取下一项任务。"),
        "last_event": "dashboard_next_action", "last_event_at": "", "elapsed_seconds": 0,
        "expected_outputs": [], "source_paths": [], "progress_steps": progress_steps(route, current_step, stage),
    }


def route_lanes(
    dashboard: dict[str, object],
    active_task: dict[str, object],
    tasks: dict[str, dict[str, object]],
    choices: list[object],
) -> list[dict[str, object]]:
    audits = dashboard.get("route_audits") if isinstance(dashboard.get("route_audits"), list) else []
    audit_by_route = {str(item.get("route") or ""): item for item in audits if isinstance(item, dict)}
    choices_by_route = _choices_by_route(choices)
    active_by_route = latest_open_task_by_route(tasks)
    lanes: list[dict[str, object]] = []
    for route in [item for item in ROUTE_ORDER if item in SUPPORTED_ROUTES]:
        lanes.append(_route_lane(route, audit_by_route.get(route, {}), active_task, active_by_route, choices_by_route))
    return lanes


def _choices_by_route(choices: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for choice in choices:
        if isinstance(choice, dict):
            route = str(choice.get("route") or "")
            counts[route] = counts.get(route, 0) + 1
    return counts


def _route_lane(
    route: str,
    audit: dict[str, object],
    active_task: dict[str, object],
    active_by_route: dict[str, dict[str, object]],
    choices_by_route: dict[str, int],
) -> dict[str, object]:
    blocking = int(audit.get("blocking_count") or 0)
    warning = int(audit.get("warning_count") or 0)
    pending = int(audit.get("pending_task_count") or 0)
    choice_count = choices_by_route.get(route, 0)
    status, message = _route_status(audit, blocking, warning, pending, choice_count)
    latest_task = active_by_route.get(route, {})
    return {
        "route": route, "label": route_label(route), "status": status,
        "active": str(active_task.get("route") or "") == route, "message": message,
        "blocking_count": blocking, "warning_count": warning, "pending_task_count": pending,
        "waiting_choice_count": choice_count, "current_step": latest_task.get("current_state", ""),
        "latest_task_id": latest_task.get("task_id", ""), "target": latest_task.get("scene_id", ""),
    }


def _route_status(
    audit: dict[str, object],
    blocking: int,
    warning: int,
    pending: int,
    choice_count: int,
) -> tuple[str, str]:
    gates = audit.get("top_blocking_gates") if isinstance(audit.get("top_blocking_gates"), list) else []
    top_gate = str(gates[0].get("message") or "") if gates and isinstance(gates[0], dict) else ""
    if blocking:
        return "blocked", top_gate or "这条路线有硬门禁没有通过。"
    if choice_count:
        return "waiting_user", "这条路线有节点需要你选择或审批。"
    if pending:
        return "pending", "这条路线还有平台 Agent 任务未完成。"
    if warning:
        return "warning", "这条路线可以继续，但有提醒需要留意。"
    return "ready", "这条路线暂时没有硬阻塞。"


def timeline_entry(root: Path, event: dict[str, object], tasks: dict[str, dict[str, object]]) -> dict[str, object]:
    task_id = str(event.get("task_id") or "")
    task = tasks.get(task_id, {})
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    route = str(data.get("route") or task.get("route") or "")
    event_type = str(event.get("event_type") or "")
    return {
        "event_type": event_type, "label": EVENT_LABELS.get(event_type, "项目事件"), "task_id": task_id,
        "route": route, "route_label": route_label(route),
        "target": str(data.get("scene_id") or task.get("scene_id") or ""),
        "created_at": str(event.get("created_at") or ""), "summary": event_summary(event_type, data, task),
        "artifact_paths": _event_artifacts(root, data),
    }


def _event_artifacts(root: Path, data: dict[str, object]) -> list[str]:
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []
    result = [str(item) for item in artifacts if str(item).strip()]
    for item in [str(data.get("completion") or ""), str(data.get("state") or "")]:
        if item:
            result.append(item)
    return [relative_path(root / item, root) if not Path(item).is_absolute() else item for item in result[:12]]


def task_summary(root: Path, task: dict[str, object], task_path: Path) -> dict[str, object]:
    task_id = str(task.get("task_id") or task_path.name.removesuffix(".task.json"))
    route = str(task.get("route") or "")
    current_state = str(task.get("current_state") or "")
    scene_id = str(task.get("scene_id") or "")
    return {
        "task_id": task_id, "route": route, "route_label": route_label(route), "target": scene_id,
        "current_step": current_state, "task_type": str(task.get("task_type") or ""),
        "status": str(task.get("status") or ""),
        "headline": headline(route, scene_id, current_state, str(task.get("status") or "issued")),
        "prompt_asset_id": str(task.get("prompt_asset_id") or ""), "task_json": relative_path(task_path, root),
        "task_markdown": relative_path(root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md", root),
    }
