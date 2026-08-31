"""Project bounded Agent transcript and tool activity without fabricating prose."""

from __future__ import annotations

from typing import Any


MAX_SESSION_TEXT = 120_000


def reduce_sessions(
    events: list[dict[str, Any]], persisted: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    sessions = _persisted_sessions(persisted)
    for event in events:
        session_id = _session_id(event)
        if not session_id:
            continue
        current = sessions.setdefault(session_id, _new_session(session_id, event))
        _apply_event(current, event)
    return sorted(sessions.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def _persisted_sessions(
    persisted: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for item in persisted or []:
        session_id = str(item.get("session_id") or "")
        if session_id:
            sessions[session_id] = {**item, "transcript": "", "tools": []}
    return sessions


def _session_id(event: dict[str, Any]) -> str:
    return str(event.get("session_id") or event.get("run_id") or "")


def _new_session(session_id: str, event: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id, "role": "worker", "runtime": "", "status": "running",
        "route": str(event.get("route") or ""), "task_id": str(event.get("task_id") or ""),
        "transcript": "", "tools": [],
    }


def _apply_event(current: dict[str, Any], event: dict[str, Any]) -> None:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    name = str(event.get("event") or "")
    current.update(
        updated_at=str(event.get("at") or ""), last_event=name,
        route=str(event.get("route") or current.get("route") or ""),
        task_id=str(event.get("task_id") or current.get("task_id") or ""),
        runtime=str(data.get("runtime") or current.get("runtime") or ""),
    )
    if name == "agent.message.delta":
        _append_transcript(current, str(data.get("text") or ""))
    if name.startswith("tool."):
        _append_tool(current, event, data)
    if name == "runner.session.finished":
        current["status"] = str(data.get("status") or "complete")


def _append_transcript(current: dict[str, Any], text: str) -> None:
    current["transcript"] = (str(current.get("transcript") or "") + text)[-MAX_SESSION_TEXT:]


def _append_tool(
    current: dict[str, Any], event: dict[str, Any], data: dict[str, Any]
) -> None:
    tools = current.setdefault("tools", [])
    if not isinstance(tools, list):
        return
    tools.append({
        "event": event.get("event"), "tool": data.get("tool"),
        "status": data.get("status"), "at": event.get("at"),
    })
    del tools[:-40]


__all__ = ["MAX_SESSION_TEXT", "reduce_sessions"]
