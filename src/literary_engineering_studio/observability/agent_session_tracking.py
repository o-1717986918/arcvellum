"""Persist public lifecycle facts for real Agent sessions."""

from __future__ import annotations

from typing import Any


_TERMINAL_STATUS = {
    "completed": "complete",
    "complete": "complete",
    "failed": "failed",
    "preflight_failed": "failed",
    "timeout": "failed",
    "cancelled": "cancelled",
    "stopped": "stopped",
}


def track_agent_session_event(
    store,
    *,
    project_root: str,
    role: str,
    runtime: str,
    controller_id: str,
    task_id: str = "",
    route: str = "",
    event: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """Project one runtime event into the durable, user-safe session ledger."""

    session_id = str(data.get("session_id") or "").strip()
    if not session_id:
        return None
    if event in {"agent.message.delta", "runner.session.status", "usage.updated"}:
        return None
    current = _read_existing(store, session_id)
    raw_status = str(data.get("status") or "").strip().lower()
    status = _status_for(event, raw_status, current)
    retry_count = int(current.get("retry_count") or 0) if current else 0
    if event == "repair.started":
        retry_count = max(retry_count + 1, int(data.get("attempt") or 0))
    return store.upsert_agent_session(
        session_id,
        project_root=project_root,
        role=role,
        runtime=runtime,
        model=str(data.get("model") or ""),
        status=status,
        task_id=str(data.get("task_id") or task_id or ""),
        route=str(data.get("route") or route or ""),
        controller_id=controller_id,
        last_event=event,
        last_message=_public_message(event, data),
        retry_count=retry_count,
    )


def _read_existing(store, session_id: str) -> dict[str, Any]:
    try:
        return store.read_agent_session(session_id)
    except FileNotFoundError:
        return {}


def _status_for(event: str, raw_status: str, current: dict[str, Any]) -> str:
    if event in {"runner.session.finished", "advisor.session.finished", "steward.session.finished"}:
        return _TERMINAL_STATUS.get(raw_status, "complete")
    if event == "runner.process.completed":
        return _TERMINAL_STATUS.get(raw_status, "complete")
    if event == "run.stopped":
        return "cancelled"
    if event in {"advisor.session.idle"}:
        return "idle"
    if event in {"worker.human.required", "advisor.session.waiting_human"}:
        return "waiting_human"
    if event in {"runner.session.created", "advisor.session.created", "steward.session.created"}:
        return "queued"
    if event.endswith(".failed") or raw_status == "failed":
        return "failed"
    if event in {
        "runner.session.started",
        "advisor.session.started",
        "steward.session.started",
        "tool.started",
        "agent.message.delta",
        "repair.started",
        "validation.failed",
        "validation.passed",
    }:
        return "running"
    return str(current.get("status") or "running")


def _public_message(event: str, data: dict[str, Any]) -> str:
    explicit = str(data.get("public_message") or "").strip()
    if explicit:
        return explicit[:600]
    if event in {"runner.session.finished", "advisor.session.finished", "steward.session.finished"}:
        status = str(data.get("status") or "").strip().lower()
        reason = str(data.get("reason") or "").strip().lower()
        if status == "failed":
            return {
                "timeout": "会话等待模型响应超时，已安全停止。",
                "preflight_failed": "产物未通过确定性预检，会话已停止并保留修订证据。",
                "model_error": "模型返回未能形成可验收产物，会话已停止。",
                "decision_error": "受托决定未形成有效结果，会话已停止。",
                "advisor_error": "项目顾问未能完成本次答复。",
            }.get(reason, "会话未能完成当前动作，错误详情已保留在诊断记录中。")
        if status == "cancelled":
            return "会话已按停止请求取消。"
    messages = {
        "runner.session.created": "主创会话已经创建，正在准备任务资料。",
        "runner.session.started": "主创正在执行当前正式任务。",
        "tool.started": "正在运行任务允许的工具步骤。",
        "repair.started": "产物未通过确定性预检，正在执行受控修订。",
        "validation.failed": "当前产物仍需修订。",
        "validation.passed": "当前产物已通过确定性预检。",
        "advisor.session.created": "项目顾问会话已经建立。",
        "advisor.session.started": "项目顾问正在阅读只读快照并组织答复。",
        "advisor.session.idle": "项目顾问已完成本次答复，保留会话等待继续交流。",
        "steward.session.created": "受托决策会话已经建立。",
        "steward.session.started": "受托决策者正在比较已授权选项。",
        "runner.session.finished": "主创会话已经结束。",
        "advisor.session.finished": "项目顾问会话已经结束。",
        "steward.session.finished": "受托决策会话已经结束。",
    }
    return messages.get(event, "Agent 会话状态已更新。")
