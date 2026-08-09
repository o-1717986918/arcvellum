"""Session completion and silence-policy polling for OpenCode."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


def wait_for_observed_session(
    waiter: Callable[..., str],
    client: Any,
    session_id: str,
    deadline: float,
    cancellation: threading.Event,
    *,
    timeout_policy: Any,
    observer: Any,
    emit: Callable[[str, dict[str, Any]], None],
    started_at: float,
    last_activity: Callable[[], float],
) -> str:
    return waiter(
        client,
        session_id,
        deadline,
        cancellation,
        first_event_timeout=timeout_policy.first_event_seconds,
        inter_event_timeout=timeout_policy.inter_event_seconds,
        has_public_activity=lambda: observer.public_activity,
        has_runtime_activity=lambda: observer.runtime_activity,
        has_productive_activity=lambda: observer.productive_activity,
        on_productive_stall=lambda elapsed: emit(
            "runner.no_productive_progress",
            {
                "session_id": session_id,
                "elapsed_ms": round(elapsed * 1000),
                "runtime_active": True,
                "productive_progress": False,
            },
        ),
        started_at=started_at,
        last_activity=last_activity,
    )


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
    has_runtime_activity: Callable[[], bool] | None = None,
    has_productive_activity: Callable[[], bool] | None = None,
    on_productive_stall: Callable[[float], None] | None = None,
    started_at: float | None = None,
    last_activity: Callable[[], float] | None = None,
) -> str:
    seen_busy = False
    productive_stall_reported = False
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
        now = time.monotonic()
        timeout_status = _silence_status(
            now=now,
            started=started,
            idle_timeout=idle_timeout,
            first_event_timeout=first_event_timeout,
            inter_event_timeout=inter_event_timeout,
            has_public_activity=has_public_activity,
            has_runtime_activity=has_runtime_activity,
            last_activity=last_activity,
        )
        if timeout_status:
            return timeout_status
        if _productive_stall_due(
            reported=productive_stall_reported,
            now=now,
            started=started,
            threshold=first_event_timeout,
            has_runtime_activity=has_runtime_activity,
            has_productive_activity=has_productive_activity,
            callback=on_productive_stall,
        ):
            productive_stall_reported = True
            assert on_productive_stall is not None
            on_productive_stall(now - started)
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
    has_runtime_activity: Callable[[], bool] | None,
    last_activity: Callable[[], float] | None,
) -> str:
    if has_runtime_activity is not None:
        return _runtime_silence_status(
            now=now,
            started=started,
            first_event_timeout=first_event_timeout,
            inter_event_timeout=inter_event_timeout,
            active=has_runtime_activity(),
            last_activity=last_activity,
        )
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


def _runtime_silence_status(
    *,
    now: float,
    started: float,
    first_event_timeout: int | float | None,
    inter_event_timeout: int | float | None,
    active: bool,
    last_activity: Callable[[], float] | None,
) -> str:
    if not active:
        return "first_event_timeout" if first_event_timeout and now - started >= float(first_event_timeout) else ""
    return (
        "idle_timeout"
        if inter_event_timeout and last_activity and now - last_activity() >= float(inter_event_timeout)
        else ""
    )


def _productive_stall_due(
    *,
    reported: bool,
    now: float,
    started: float,
    threshold: int | float | None,
    has_runtime_activity: Callable[[], bool] | None,
    has_productive_activity: Callable[[], bool] | None,
    callback: Callable[[float], None] | None,
) -> bool:
    return bool(
        not reported
        and callback is not None
        and has_runtime_activity is not None
        and has_runtime_activity()
        and has_productive_activity is not None
        and not has_productive_activity()
        and threshold
        and now - started >= float(threshold)
    )
