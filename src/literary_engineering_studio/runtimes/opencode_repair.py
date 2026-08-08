"""Same-session deterministic repair loop for the OpenCode transport."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Callable

from .base import RuntimeFailureKind, RuntimeResult


@dataclass(frozen=True)
class RepairLoopEnvironment:
    client: Any
    session_id: str
    model: str
    agent_id: str
    timeout: int
    cancellation: Any
    settings: dict[str, object]
    emit: Callable[[str, dict[str, Any]], None]
    mark_activity: Callable[[], None]
    last_activity: Callable[[], float]
    wait_for_session: Callable[..., str]
    prompt_builder: Callable[[Any, int, int], Any] | None
    turn_finalizer: Callable[[], dict[str, object]] | None


@dataclass(frozen=True)
class RepairLoopResult:
    status: str
    repairs: int
    preflight: Any
    payload: dict[str, Any]


def run_preflight_repair_loop(
    environment: RepairLoopEnvironment,
    *,
    output_validator: Callable[[], Any] | None,
    max_repairs: int,
) -> RepairLoopResult:
    repairs = 0
    final_preflight = None
    maximum = max(0, int(max_repairs))
    if output_validator is None:
        return RepairLoopResult("passed", repairs, None, {})
    while True:
        final_preflight = output_validator()
        payload = _preflight_payload(
            final_preflight,
            repairs,
            maximum,
        )
        environment.emit(
            (
                "validation.passed"
                if payload.get("passed")
                else "validation.failed"
            ),
            {"kind": "sandbox-preflight", **payload},
        )
        if payload.get("passed"):
            return RepairLoopResult(
                "passed",
                repairs,
                final_preflight,
                payload,
            )
        if repairs >= maximum:
            return RepairLoopResult(
                "preflight_failed",
                repairs,
                final_preflight,
                payload,
            )
        repairs += 1
        status = _execute_repair_turn(
            environment,
            final_preflight,
            payload,
            repairs,
            maximum,
        )
        if status != "completed":
            return RepairLoopResult(
                status,
                repairs,
                final_preflight,
                payload,
            )


def run_open_code_repairs(
    *,
    client: Any,
    session_id: str,
    model: str,
    agent_id: str,
    timeout: int,
    cancellation: Any,
    settings: dict[str, object],
    emit: Callable[[str, dict[str, Any]], None],
    mark_activity: Callable[[], None],
    last_activity: Callable[[], float],
    wait_for_session: Callable[..., str],
    output_validator: Callable[[], Any] | None,
    max_repairs: int,
    repair_prompt_builder: Callable[[Any, int, int], Any] | None,
    repair_turn_finalizer: Callable[[], dict[str, object]] | None,
) -> RepairLoopResult:
    environment = RepairLoopEnvironment(
        client=client,
        session_id=session_id,
        model=model,
        agent_id=agent_id,
        timeout=timeout,
        cancellation=cancellation,
        settings=settings,
        emit=emit,
        mark_activity=mark_activity,
        last_activity=last_activity,
        wait_for_session=wait_for_session,
        prompt_builder=repair_prompt_builder,
        turn_finalizer=repair_turn_finalizer,
    )
    return run_preflight_repair_loop(
        environment,
        output_validator=output_validator,
        max_repairs=max_repairs,
    )


def repair_failure_result(
    result: RepairLoopResult,
    *,
    runtime_id: str,
    command: Any,
    client: Any,
    session_id: str,
    model: str,
    output_path: Path,
    emit: Callable[[str, dict[str, Any]], None],
) -> RuntimeResult:
    if result.status == "preflight_failed":
        output_path.write_text(
            _latest_assistant_text(client.messages(session_id)),
            encoding="utf-8",
        )
        emit(
            "runner.session.finished",
            {
                "session_id": session_id,
                "model": model,
                "status": "failed",
                "reason": "preflight_failed",
            },
        )
        emit(
            "runner.process.completed",
            {
                "runner_id": runtime_id,
                "session_id": session_id,
                "model": model,
                "status": "preflight_failed",
            },
        )
        return RuntimeResult(
            runtime_id,
            "preflight_failed",
            2,
            command,
            output_path,
            "sandbox output still fails deterministic preflight",
            {
                "session_id": session_id,
                "repairs": result.repairs,
                "preflight": result.payload,
                "failure_kind": RuntimeFailureKind.VALIDATION_FAILURE.value,
                "retryable": True,
            },
        )
    client.abort(session_id)
    status = (
        "cancelled" if result.status == "cancelled" else "timeout"
    )
    emit(
        "runner.session.finished",
        {
            "session_id": session_id,
            "model": model,
            "status": "cancelled" if status == "cancelled" else "failed",
            "reason": f"repair_{status}",
        },
    )
    return RuntimeResult(
        runtime_id,
        status,
        None,
        command,
        output_path,
        f"repair {status}",
        {
            "session_id": session_id,
            "failure_kind": (
                RuntimeFailureKind.IDLE_TIMEOUT.value
                if result.status in {"idle_timeout", "first_event_timeout"}
                else RuntimeFailureKind.TOTAL_TIMEOUT.value
            ),
            "retryable": True,
        },
    )


def _execute_repair_turn(
    environment: RepairLoopEnvironment,
    preflight: Any,
    payload: dict[str, Any],
    attempt: int,
    maximum: int,
) -> str:
    prepared = (
        environment.prompt_builder(preflight, attempt, max(1, maximum))
        if environment.prompt_builder is not None
        else preflight.repair_prompt(attempt, max(1, maximum))
    )
    prompt, metadata = _prepared_repair_fields(prepared)
    environment.emit(
        "repair.started",
        {
            "attempt": attempt,
            "issue_count": payload.get("issue_count", 0),
            "session_id": environment.session_id,
            **metadata,
        },
    )
    status = "failed"
    try:
        environment.client.prompt_async(
            environment.session_id,
            text=prompt,
            model=environment.model,
            agent=environment.agent_id,
        )
        deadline = time.monotonic() + min(
            300,
            max(60, int(environment.timeout) // 3),
        )
        environment.mark_activity()
        idle_timeout = max(
            30,
            int(
                environment.settings.get(
                    "repair_idle_timeout_seconds"
                )
                or 75
            ),
        )
        status = environment.wait_for_session(
            environment.client,
            environment.session_id,
            deadline,
            environment.cancellation,
            idle_timeout=idle_timeout,
            last_activity=environment.last_activity,
        )
    finally:
        _finalize_repair_turn(environment)
    if status == "completed":
        environment.emit(
            "repair.completed",
            {
                "attempt": attempt,
                "session_id": environment.session_id,
                **metadata,
            },
        )
    return status


def _preflight_payload(
    preflight: Any,
    attempt: int,
    maximum: int,
) -> dict[str, Any]:
    payload = (
        preflight.as_dict()
        if hasattr(preflight, "as_dict")
        else {"passed": bool(preflight)}
    )
    payload.update(
        {
            "attempt": attempt,
            "maximum_repairs": maximum,
        }
    )
    return payload


def _prepared_repair_fields(
    value: object,
) -> tuple[str, dict[str, object]]:
    if isinstance(value, str):
        return value, {}
    prompt = str(getattr(value, "prompt", "") or "")
    if not prompt:
        raise ValueError("repair prompt builder returned no prompt")
    event_builder = getattr(value, "event_fields", None)
    metadata = event_builder() if callable(event_builder) else {}
    if not isinstance(metadata, dict):
        raise ValueError("repair prompt event fields must be an object")
    return prompt, metadata


def _finalize_repair_turn(
    environment: RepairLoopEnvironment,
) -> None:
    if environment.turn_finalizer is None:
        return
    result = environment.turn_finalizer()
    if not isinstance(result, dict):
        raise ValueError("repair turn finalizer must return an object")
    environment.emit("repair.output_guard.finalized", result)


def _latest_assistant_text(messages: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for message in messages:
        info = (
            message.get("info")
            if isinstance(message.get("info"), dict)
            else {}
        )
        if info.get("role") != "assistant":
            continue
        current = [
            str(part.get("text") or "")
            for part in message.get("parts") or []
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        if current:
            texts = current
    return "".join(texts)


__all__ = [
    "RepairLoopEnvironment",
    "RepairLoopResult",
    "repair_failure_result",
    "run_open_code_repairs",
    "run_preflight_repair_loop",
]
