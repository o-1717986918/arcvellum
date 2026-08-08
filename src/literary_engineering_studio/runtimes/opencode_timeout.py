"""Translate OpenCode wait terminal states into structured runtime results."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Callable, Sequence

from .base import RuntimeFailureKind, RuntimeResult
from .opencode_session import SessionTimeoutPolicy


def timeout_runtime_result(
    wait_status: str,
    *,
    runtime_id: str,
    client: Any,
    session_id: str,
    model: str,
    runtime_pool: Any,
    lease: Any,
    command: Sequence[str],
    output_path: Path,
    total_timeout: int,
    policy: SessionTimeoutPolicy,
    emit: Callable[[str, dict[str, Any]], None],
) -> RuntimeResult | None:
    if wait_status == "timeout":
        client.abort(session_id)
        emit("runner.session.finished", _terminal_event(session_id, model, "timeout"))
        return RuntimeResult(
            runtime_id,
            "timeout",
            None,
            tuple(command),
            output_path,
            f"task exceeded its total runtime limit of {total_timeout}s",
            _metadata(RuntimeFailureKind.TOTAL_TIMEOUT, False, session_id),
        )
    if wait_status not in {"first_event_timeout", "idle_timeout"}:
        return None
    client.abort(session_id)
    kind, limit = _silence_kind_and_limit(wait_status, policy)
    restarted = (
        runtime_pool.invalidate(lease, reason=f"session-{wait_status}")
        if lease is not None and runtime_pool is not None
        else False
    )
    event = _terminal_event(session_id, model, wait_status)
    event.update({"silence_timeout_seconds": limit, "service_restarted": restarted})
    emit("runner.session.finished", event)
    message = (
        f"model produced no visible activity within {limit}s"
        if wait_status == "first_event_timeout"
        else f"model produced no further activity for {limit}s"
    )
    metadata = _metadata(kind, True, session_id)
    metadata.update({"silence_timeout_seconds": limit, "service_restarted": restarted})
    return RuntimeResult(runtime_id, "timeout", None, tuple(command), output_path, message, metadata)


def _silence_kind_and_limit(
    status: str,
    policy: SessionTimeoutPolicy,
) -> tuple[RuntimeFailureKind, int]:
    if status == "first_event_timeout":
        return RuntimeFailureKind.FIRST_EVENT_TIMEOUT, policy.first_event_seconds
    return RuntimeFailureKind.IDLE_TIMEOUT, policy.inter_event_seconds


def _terminal_event(session_id: str, model: str, reason: str) -> dict[str, Any]:
    return {"session_id": session_id, "model": model, "status": "failed", "reason": reason}


def _metadata(
    kind: RuntimeFailureKind,
    retryable: bool,
    session_id: str,
) -> dict[str, Any]:
    return {"failure_kind": kind.value, "retryable": retryable, "session_id": session_id}
