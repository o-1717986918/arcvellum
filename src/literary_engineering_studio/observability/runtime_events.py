"""Normalize provider-specific Agent Runner events without storing hidden reasoning."""

from __future__ import annotations

from typing import Any


def normalize_opencode_event(
    payload: dict[str, Any],
    *,
    session_id: str = "",
    tool_states: dict[str, str] | None = None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    event = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    if not isinstance(event, dict):
        return ()
    kind = str(event.get("type") or "")
    properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    event_session = _session_id(properties)
    if session_id and event_session and event_session != session_id:
        return ()
    if kind in {"message.part.updated", "message.part.delta"}:
        return _message_part_event(properties, event_session, tool_states)
    return _non_part_event(kind, properties, event_session)


def _message_part_event(
    properties: dict[str, Any],
    session_id: str,
    tool_states: dict[str, str] | None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    part = properties.get("part") if isinstance(properties.get("part"), dict) else {}
    part_type = str(part.get("type") or "")
    delta = properties.get("delta")
    if part_type == "reasoning":
        return (("runner.reasoning.activity", {"session_id": session_id, "delta_events": 1, "delta_characters": len(delta) if isinstance(delta, str) else 0}),)
    if part_type == "text" and isinstance(delta, str) and delta:
        return (("agent.message.delta", {"text": delta, "session_id": session_id}),)
    if part_type == "tool":
        return _tool_part_event(part, tool_states)
    return ()


def _tool_part_event(
    part: dict[str, Any],
    tool_states: dict[str, str] | None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    status = str(state.get("status") or "")
    tool = str(part.get("tool") or part.get("name") or "")
    call_id = str(part.get("callID") or part.get("id") or "")
    previous = tool_states.get(call_id) if tool_states is not None and call_id else ""
    if status in {"pending", "running"}:
        return _tool_started_event(tool, call_id, status, previous, tool_states)
    if status in {"completed", "error"}:
        return _tool_finished_event(tool, call_id, status, previous, tool_states)
    return ()


def _tool_started_event(
    tool: str,
    call_id: str,
    status: str,
    previous: str,
    tool_states: dict[str, str] | None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    if previous in {"pending", "running", "completed", "error"}:
        return ()
    if tool_states is not None and call_id:
        tool_states[call_id] = status
    return (("tool.started", {"tool": tool, "tool_use_id": call_id}),)


def _tool_finished_event(
    tool: str,
    call_id: str,
    status: str,
    previous: str,
    tool_states: dict[str, str] | None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    if previous == status:
        return ()
    if tool_states is not None and call_id:
        tool_states[call_id] = status
    name = "tool.completed" if status == "completed" else "tool.denied"
    return ((name, {"tool": tool, "tool_use_id": call_id, "status": status}),)


def _non_part_event(
    kind: str,
    properties: dict[str, Any],
    session_id: str,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    if kind == "message.updated":
        info = properties.get("info") if isinstance(properties.get("info"), dict) else {}
        return _usage_event(info, session_id)
    if kind == "session.status":
        status = properties.get("status") if isinstance(properties.get("status"), dict) else {}
        return (("runner.session.status", {"session_id": session_id, "status": str(status.get("type") or "")}),)
    if kind in {"session.error", "permission.asked", "permission.updated"}:
        return (("runner.warning", {"session_id": session_id, "kind": kind, "detail": _public(properties)}),)
    if kind in {"file.edited", "file.watcher.updated"}:
        return (("file.changed", {"session_id": session_id, "path": str(properties.get("file") or properties.get("path") or "")}),)
    if kind == "server.connected":
        return (("runner.ready", {"runner_id": "opencode"}),)
    return ()


def _usage_event(info: dict[str, Any], session_id: str) -> tuple[tuple[str, dict[str, Any]], ...]:
    if info.get("role") != "assistant" or not isinstance(info.get("tokens"), dict):
        return ()
    return (
        (
            "usage.updated",
            {
                "session_id": session_id,
                "usage_id": str(info.get("id") or info.get("messageID") or ""),
                "provider": str(info.get("providerID") or ""),
                "model": str(info.get("modelID") or ""),
                "usage": info.get("tokens") or {},
                "cost_usd": info.get("cost"),
            },
        ),
    )


def merge_usage_summary(summary: dict[str, Any], data: dict[str, Any]) -> None:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    summary.update(usage)
    summary["cost_usd"] = data.get("cost_usd")


def _session_id(properties: dict[str, Any]) -> str:
    value = properties.get("sessionID") or properties.get("session_id")
    if value:
        return str(value)
    info = properties.get("info") if isinstance(properties.get("info"), dict) else {}
    part = properties.get("part") if isinstance(properties.get("part"), dict) else {}
    return str(info.get("sessionID") or part.get("sessionID") or "")


def _public(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _public(item)
            for key, item in value.items()
            if str(key).lower() not in {"reasoning", "thinking", "system", "prompt"}
        }
    if isinstance(value, list):
        return [_public(item) for item in value]
    return value
