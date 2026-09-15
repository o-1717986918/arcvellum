"""Durable active-turn projection for Project Agent conversations."""

from __future__ import annotations

from typing import Any


def turn_reference(message: object) -> tuple[str, str] | None:
    if not isinstance(message, dict):
        return None
    payload = message.get("payload")
    if not isinstance(payload, dict):
        return None
    job_id = str(payload.get("job_id") or "").strip()
    if not job_id:
        return None
    return job_id, str(payload.get("turn_id") or "")


def active_turn_payload(
    job: dict[str, Any],
    job_id: str,
    fallback_turn_id: str,
    session_id: str,
) -> dict[str, Any] | None:
    request_value = job.get("request")
    request = request_value if isinstance(request_value, dict) else {}
    if request.get("kind") != "project-agent-turn":
        return None
    if str(request.get("session_id") or "") != session_id:
        return None
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "stopping"}:
        return None
    return {
        "job_id": job_id,
        "turn_id": str(request.get("turn_id") or fallback_turn_id),
        "status": status,
        "started_at": str(job.get("started_at") or job.get("created_at") or ""),
    }


__all__ = ["active_turn_payload", "turn_reference"]
