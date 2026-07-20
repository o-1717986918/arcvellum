"""Normalize provider-specific Agent Runner events without storing hidden reasoning."""

from __future__ import annotations

from typing import Any


def normalize_opencode_event(payload: dict[str, Any], *, session_id: str = "") -> tuple[tuple[str, dict[str, Any]], ...]:
    event = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    if not isinstance(event, dict):
        return ()
    kind = str(event.get("type") or "")
    properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    event_session = _session_id(properties)
    if session_id and event_session and event_session != session_id:
        return ()
    if kind in {"message.part.updated", "message.part.delta"}:
        part = properties.get("part") if isinstance(properties.get("part"), dict) else {}
        part_type = str(part.get("type") or "")
        if part_type == "reasoning":
            return ()
        if part_type == "text":
            delta = properties.get("delta")
            if isinstance(delta, str) and delta:
                return (("agent.message.delta", {"text": delta, "session_id": event_session}),)
        if part_type == "tool":
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            status = str(state.get("status") or "")
            tool = str(part.get("tool") or part.get("name") or "")
            call_id = str(part.get("callID") or part.get("id") or "")
            if status in {"pending", "running"}:
                return (("tool.started", {"tool": tool, "tool_use_id": call_id}),)
            if status in {"completed", "error"}:
                name = "tool.completed" if status == "completed" else "tool.denied"
                return ((name, {"tool": tool, "tool_use_id": call_id, "status": status}),)
    if kind == "message.updated":
        info = properties.get("info") if isinstance(properties.get("info"), dict) else {}
        if info.get("role") == "assistant" and isinstance(info.get("tokens"), dict):
            return (
                (
                    "usage.updated",
                    {
                        "session_id": event_session,
                        "provider": str(info.get("providerID") or ""),
                        "model": str(info.get("modelID") or ""),
                        "usage": info.get("tokens") or {},
                        "cost_usd": info.get("cost"),
                    },
                ),
            )
    if kind == "session.status":
        status = properties.get("status") if isinstance(properties.get("status"), dict) else {}
        return (("runner.session.status", {"session_id": event_session, "status": str(status.get("type") or "")}),)
    if kind in {"session.error", "permission.asked", "permission.updated"}:
        return (("runner.warning", {"session_id": event_session, "kind": kind, "detail": _public(properties)}),)
    if kind in {"file.edited", "file.watcher.updated"}:
        return (("file.changed", {"session_id": event_session, "path": str(properties.get("file") or properties.get("path") or "")}),)
    if kind == "server.connected":
        return (("runner.ready", {"runner_id": "opencode"}),)
    return ()


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
