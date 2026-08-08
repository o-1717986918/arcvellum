"""Session completion and silence-policy polling for OpenCode."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


def wait_for_session(
    client,
    session_id: str,
    deadline: float,
    cancellation: threading.Event,
    *,
    idle_timeout: int | float | None = None,
    first_event_timeout: int | float | None = None,
    inter_event_timeout: int | float | None = None,
    has_public_activity: Callable[[], bool] | None = None,
    started_at: float | None = None,
    last_activity: Callable[[], float] | None = None,
) -> str:
    seen_busy = False
    started = started_at if started_at is not None else time.monotonic()
    while time.monotonic() < deadline:
        if cancellation.is_set():
            client.abort(session_id)
            return "cancelled"
        state = _session_state(client, session_id)
        if state in {"busy", "retry"}:
            seen_busy = True
        if seen_busy and state in {"idle", ""}:
            return "completed"
        timeout_status = _silence_status(
            now=time.monotonic(),
            started=started,
            idle_timeout=idle_timeout,
            first_event_timeout=first_event_timeout,
            inter_event_timeout=inter_event_timeout,
            has_public_activity=has_public_activity,
            last_activity=last_activity,
        )
        if timeout_status:
            return timeout_status
        time.sleep(0.2)
    return "timeout"


def _session_state(client, session_id: str) -> str:
    status_map = client.session_status()
    status = status_map.get(session_id) if isinstance(status_map, dict) else None
    return str(status.get("type") or "") if isinstance(status, dict) else ""


def _silence_status(
    *,
    now: float,
    started: float,
    idle_timeout: int | float | None,
    first_event_timeout: int | float | None,
    inter_event_timeout: int | float | None,
    has_public_activity: Callable[[], bool] | None,
    last_activity: Callable[[], float] | None,
) -> str:
    if has_public_activity is None:
        if idle_timeout and last_activity and now - last_activity() >= float(idle_timeout):
            return "idle_timeout"
        return ""
    if not has_public_activity():
        return (
            "first_event_timeout"
            if first_event_timeout and now - started >= float(first_event_timeout)
            else ""
        )
    return (
        "idle_timeout"
        if inter_event_timeout and last_activity and now - last_activity() >= float(inter_event_timeout)
        else ""
    )
