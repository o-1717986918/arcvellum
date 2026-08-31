"""Project bounded Agent transcript and tool activity without fabricating prose."""

from __future__ import annotations

from typing import Any


MAX_SESSION_TEXT = 120_000


def reduce_sessions(
    events: list[dict[str, Any]], persisted: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for item in persisted or []:
        session_id = str(item.get("session_id") or "")
        if session_id:
            sessions[session_id] = {**item, "transcript": "", "tools": []}
    for event in events:
        session_id = str(event.get("session_id") or event.get("run_id") or "")
        if not session_id:
            continue
        current = sessions.setdefault(
            session_id,
            {
                "session_id": session_id,
                "role": "worker",
                "runtime": "",
                "status": "running",
                "route": str(event.get("route") or ""),
                "task_id": str(event.get("task_id") or ""),
                "transcript": "",
                "tools": [],
            },
        )
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        current["updated_at"] = str(event.get("at") or "")
        current["last_event"] = str(event.get("event") or "")
        current["route"] = str(event.get("route") or current.get("route") or "")
        current["task_id"] = str(event.get("task_id") or current.get("task_id") or "")
        current["runtime"] = str(data.get("runtime") or current.get("runtime") or "")
        if event.get("event") == "agent.message.delta":
            text = str(data.get("text") or "")
            current["transcript"] = (str(current.get("transcript") or "") + text)[-MAX_SESSION_TEXT:]
        if str(event.get("event") or "").startswith("tool."):
            tools = current.setdefault("tools", [])
            if isinstance(tools, list):
                tools.append({
                    "event": event.get("event"),
                    "tool": data.get("tool"),
                    "status": data.get("status"),
                    "at": event.get("at"),
                })
                del tools[:-40]
        if event.get("event") == "runner.session.finished":
            current["status"] = str(data.get("status") or "complete")
    return sorted(sessions.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)


__all__ = ["MAX_SESSION_TEXT", "reduce_sessions"]
