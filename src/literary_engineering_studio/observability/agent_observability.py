"""User-safe projection of Agent Runtime activity.

The projection deliberately reports visible task stages and evidence only. It does
not serialize private prompts, model reasoning, credentials, filesystem paths, or
unbounded tool output.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA = "arcvellum/agent-observability/v2"


def build_agent_observability(
    project_root: str,
    autopilot_status: dict[str, Any],
    events: list[dict[str, Any]],
    dashboard: dict[str, Any],
    sessions: list[dict[str, Any]] | None = None,
    services: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    run = autopilot_status.get("run") if isinstance(autopilot_status.get("run"), dict) else {}
    current_task = dashboard.get("current_task") if isinstance(dashboard.get("current_task"), dict) else {}
    visible_events = [_visible_event(item) for item in events[-18:] if isinstance(item, dict)]
    active = _active_task(run, current_task, visible_events)
    visible_sessions = [_visible_session(item) for item in (sessions or []) if isinstance(item, dict)]
    visible_services = [_visible_service(item) for item in (services or []) if isinstance(item, dict)]
    source = {
        "run": run,
        "events": visible_events,
        "task": current_task,
        "sessions": visible_sessions,
        "services": visible_services,
    }
    status = "active" if (
        run and str(run.get("status")) == "running"
        or any(item["status"] in {"queued", "running", "waiting", "waiting_human"} for item in visible_sessions)
    ) else "idle"
    return {
        "ok": True,
        "schema": SCHEMA,
        "project_root": project_root,
        "status": status,
        "active_task": active,
        "controller": _controller(run),
        "services": visible_services,
        "sessions": visible_sessions,
        "recent_events": visible_events,
        "revision": _digest(source),
    }


def _active_task(run: dict[str, Any], task: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not run and not task:
        return None
    latest = events[-1] if events else {}
    status = str(run.get("status") or "waiting")
    return {
        "role": "主创执行者",
        "runtime": str(run.get("runtime") or "未启动"),
        "route": str(run.get("current_route") or task.get("route") or ""),
        "task_id": str(run.get("current_task_id") or task.get("task_id") or ""),
        "status": status,
        "stage": str(latest.get("stage") or _status_stage(status)),
        "message": str(latest.get("message") or _status_message(status)),
        "tasks_completed": _integer(run.get("tasks_completed")),
        "failures": _integer(run.get("failures")),
    }


def _controller(run: dict[str, Any]) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        "run_id": _short_id(run.get("run_id")),
        "status": str(run.get("status") or ""),
        "route": str(run.get("current_route") or ""),
        "task_id": str(run.get("current_task_id") or ""),
        "tasks_completed": _integer(run.get("tasks_completed")),
        "stalled_cycles": _integer(run.get("stalled_cycles")),
        "last_progress_at": str(run.get("last_progress_at") or ""),
    }


def _visible_session(item: dict[str, Any]) -> dict[str, Any]:
    status = str(item.get("status") or "idle")
    started_at = str(item.get("started_at") or "")
    finished_at = str(item.get("finished_at") or "")
    return {
        "session_id": _short_id(item.get("session_id")),
        "role": _role_label(item.get("role")),
        "role_id": str(item.get("role") or ""),
        "runtime": str(item.get("runtime") or ""),
        "model": str(item.get("model") or ""),
        "status": status,
        "route": str(item.get("route") or ""),
        "task_id": str(item.get("task_id") or ""),
        "event_count": _integer(item.get("event_count")),
        "retry_count": _integer(item.get("retry_count")),
        "last_event": str(item.get("last_event") or ""),
        "last_message": _safe_message(item.get("last_message"), _session_message(status)),
        "started_at": started_at,
        "updated_at": str(item.get("updated_at") or ""),
        "finished_at": finished_at,
        "elapsed_seconds": _elapsed_seconds(started_at, finished_at),
    }


def _visible_service(item: dict[str, Any]) -> dict[str, Any]:
    healthy = bool(item.get("healthy"))
    return {
        "role": _role_label(item.get("role")),
        "role_id": str(item.get("role") or ""),
        "model": str(item.get("model") or ""),
        "status": "failed" if not healthy else "busy" if _integer(item.get("active_leases")) else "warm",
        "healthy": healthy,
        "active_leases": _integer(item.get("active_leases")),
        "restart_count": _integer(item.get("restart_count")),
        "started_at": str(item.get("started_at") or ""),
    }


def _visible_event(item: dict[str, Any]) -> dict[str, Any]:
    event = str(item.get("event") or "")
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    stage, message = _event_stage(event, data)
    return {
        "sequence": _integer(item.get("sequence")),
        "at": str(item.get("at") or ""),
        "event": event,
        "stage": stage,
        "message": message,
        "task_id": str(data.get("task_id") or ""),
        "route": str(data.get("route") or ""),
    }


def _event_stage(event: str, data: dict[str, Any]) -> tuple[str, str]:
    mapping = {
        "route.entered": ("进入创作路线", "正在检查这一条路线需要的前置条件。"),
        "route.dependency_entered": ("补齐前置条件", "正在先处理当前任务依赖的正式证据。"),
        "route.ready": ("路线已就绪", "前置证据已满足，可以领取下一项正式任务。"),
        "worker.task.selecting": ("领取任务", "正在从状态机中领取下一项允许执行的任务。"),
        "worker.task.opened": ("读取任务包", "正在读取任务指定的资料与交付要求。"),
        "worker.core.command_started": ("运行正式步骤", "正在执行当前任务要求的正式 CLI 步骤。"),
        "worker.core.command_completed": ("验证步骤结果", "正式步骤已返回，正在继续核验产物。"),
        "worker.runner.started": ("主创正在工作", "主创执行者正在依据任务包创作、审查或整理候选。"),
        "worker.human.required": ("等待你的决定", "这一步需要由你确认，系统不会替你伪造批准。"),
        "task.recovery_started": ("恢复上次任务", "正在从已保存的任务状态恢复。"),
        "task.recovery_succeeded": ("恢复完成", "已恢复可验证产物，继续执行前仍会检查门禁。"),
        "task.failed": ("任务暂停", "本轮任务没有通过验证，等待处理后可从原处继续。"),
        "decision.started": ("评估受托决定", "受控决策代理正在比较已有选项，不会替代你的未授权选择。"),
        "decision.delegated": ("已记录受托决定", "已将可审计的决定写入项目的正式记录。"),
        "autopilot.paused": ("自动推进暂停", "自动推进在当前安全节点暂停。"),
        "autopilot.authorization_updated": ("授权已续期", "新的授权范围已经写入当前运行，并从新的时间窗口继续计算。"),
        "autopilot.resumed": ("自动推进恢复", "已从暂停点重新领取允许执行的正式任务。"),
        "autopilot.completed": ("本轮推进完成", "这一轮已完成，新的路线状态会重新计算。"),
    }
    if event in mapping:
        return mapping[event]
    if event.endswith("failed"):
        return "任务暂停", _safe_message(data.get("message"), "某一步没有通过验证。")
    if event.endswith("completed"):
        return "完成一步", "已完成一个可验证步骤，正在更新路线状态。"
    return "状态更新", _safe_message(data.get("message"), "正在更新项目任务状态。")


def _status_stage(status: str) -> str:
    return {"running": "主创正在工作", "paused": "等待继续", "blocked": "等待处理", "failed": "本轮停止", "complete": "本轮完成"}.get(status, "等待任务")


def _status_message(status: str) -> str:
    return {"running": "任务仍在受控执行，新的可见状态会持续出现。", "paused": "可以在确认后从这个安全节点继续。", "blocked": "先处理当前阻塞证据，系统不会跳过门禁。"}.get(status, "当前没有正在执行的任务。")


def _session_message(status: str) -> str:
    return {
        "queued": "会话正在等待运行。",
        "running": "会话正在执行当前任务。",
        "waiting": "会话正在等待上游结果。",
        "waiting_human": "会话正在等待你的决定。",
        "idle": "会话保持可复用，当前没有在生成内容。",
        "failed": "会话未能完成当前动作。",
        "cancelled": "会话已取消。",
        "complete": "会话已完成并归档。",
    }.get(status, "会话状态已更新。")


def _role_label(value: object) -> str:
    return {
        "worker": "主创执行者",
        "advisor": "项目顾问",
        "steward": "受托决策者",
    }.get(str(value or ""), str(value or "Agent"))


def _short_id(value: object) -> str:
    text = str(value or "")
    if len(text) <= 12:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    return f"{text[:4]}…{digest}"


def _elapsed_seconds(started_at: str, finished_at: str) -> int:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        ended = datetime.fromisoformat(finished_at.replace("Z", "+00:00")) if finished_at else datetime.now(timezone.utc)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=timezone.utc)
        return max(0, int((ended - started).total_seconds()))
    except (TypeError, ValueError):
        return 0


def _safe_message(value: object, fallback: str) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if not text:
        return fallback
    # Internal tracebacks and absolute paths are not presentation data.
    if "Traceback" in text or re.search(r"\b[A-Za-z]:[/\\]", text) or text.startswith(("/", "\\\\")):
        return fallback
    return text[:300]


def _integer(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
