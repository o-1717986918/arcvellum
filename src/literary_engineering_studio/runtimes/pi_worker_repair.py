"""Fresh-process deterministic repair loop for the bounded Pi Worker."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any
from collections.abc import Callable

from .base import RuntimeFailureKind, RuntimeResult


def run_pi_worker_repairs(
    initial_result: RuntimeResult,
    *,
    run_root: Path,
    output_validator: Callable[[], Any] | None,
    max_repairs: int,
    repair_prompt_builder: Callable[[Any, int, int], Any] | None,
    repair_turn_finalizer: Callable[[], dict[str, object]] | None,
    run_turn: Callable[[Path, Path, tuple[str, ...], str], RuntimeResult],
    emit: Callable[[str, dict[str, Any]], None],
) -> RuntimeResult:
    """Run bounded issue-focused repairs in fresh processes within one workspace."""

    if initial_result.status != "completed" or output_validator is None:
        return initial_result
    maximum = max(0, int(max_repairs))
    result = initial_result
    previous_digest = ""
    for completed_repairs in range(maximum + 1):
        preflight = output_validator()
        payload = _preflight_payload(preflight, completed_repairs, maximum)
        emit(
            "validation.passed" if payload["passed"] else "validation.failed",
            {"kind": "sandbox-preflight", **payload},
        )
        if payload["passed"]:
            return _with_repair_metadata(
                result,
                status="completed",
                repairs=completed_repairs,
                preflight=payload,
            )
        digest = _preflight_digest(payload)
        if completed_repairs and digest == previous_digest:
            emit(
                "repair.no_progress",
                {
                    "attempt": completed_repairs,
                    "reason": "identical-preflight-digest",
                    **payload,
                },
            )
            return _repair_failure(
                result,
                message="Pi repair made no deterministic preflight progress",
                repairs=completed_repairs,
                preflight=payload,
                failure_kind=RuntimeFailureKind.NO_PROGRESS,
                retryable=False,
            )
        previous_digest = digest
        if completed_repairs >= maximum or repair_prompt_builder is None:
            return _repair_failure(
                result,
                message=_preflight_message(payload),
                repairs=completed_repairs,
                preflight=payload,
                failure_kind=RuntimeFailureKind.VALIDATION_FAILURE,
                retryable=completed_repairs < maximum,
            )

        attempt = completed_repairs + 1
        result = _execute_repair_turn(
            preflight=preflight,
            attempt=attempt,
            maximum=maximum,
            run_root=run_root,
            repair_prompt_builder=repair_prompt_builder,
            repair_turn_finalizer=repair_turn_finalizer,
            run_turn=run_turn,
            emit=emit,
        )
        if result.status != "completed":
            return _with_repair_metadata(
                result,
                status=result.status,
                repairs=attempt,
                preflight=payload,
            )
    return result


def _execute_repair_turn(
    *,
    preflight: Any,
    attempt: int,
    maximum: int,
    run_root: Path,
    repair_prompt_builder: Callable[[Any, int, int], Any],
    repair_turn_finalizer: Callable[[], dict[str, object]] | None,
    run_turn: Callable[[Path, Path, tuple[str, ...], str], RuntimeResult],
    emit: Callable[[str, dict[str, Any]], None],
) -> RuntimeResult:
    prepared = repair_prompt_builder(preflight, attempt, maximum)
    attempt_root = run_root / "repairs" / f"attempt-{attempt:02d}" / "pi-worker"
    attempt_root.mkdir(parents=True, exist_ok=True)
    prompt_path = attempt_root / "AGENT_REPAIR_TASK.md"
    prompt_path.write_text(str(prepared.prompt), encoding="utf-8")
    fields = prepared.event_fields() if hasattr(prepared, "event_fields") else {}
    emit("repair.started", {"attempt": attempt, "maximum": maximum, **fields})
    try:
        targets = tuple(
            str(item).strip()
            for item in getattr(prepared, "repair_targets", ())
            if str(item).strip()
        )
        reasoning_level = str(getattr(prepared, "reasoning_level", "") or "")
        result = run_turn(prompt_path, attempt_root, targets, reasoning_level)
        metadata = dict(result.metadata or {})
        metadata["repair_reasoning_level"] = reasoning_level
        return replace(result, metadata=metadata)
    finally:
        finalized = repair_turn_finalizer() if repair_turn_finalizer else {}
        emit("repair.finished", {"attempt": attempt, **finalized})


def _preflight_payload(preflight: Any, repairs: int, maximum: int) -> dict[str, Any]:
    raw = preflight.as_dict() if hasattr(preflight, "as_dict") else {}
    issues = raw.get("issues") if isinstance(raw, dict) else []
    issue_rows = issues if isinstance(issues, list) else []
    return {
        "passed": bool(getattr(preflight, "passed", False)),
        "repairs": repairs,
        "maximum_repairs": maximum,
        "issue_count": len(issue_rows),
        "issues": issue_rows[:50],
    }


def _preflight_digest(payload: dict[str, Any]) -> str:
    semantic = {
        "passed": payload.get("passed"),
        "issues": payload.get("issues"),
    }
    return json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _preflight_message(payload: dict[str, Any]) -> str:
    issues = payload.get("issues")
    rows = issues if isinstance(issues, list) else []
    details = "; ".join(str(item.get("message") or "") for item in rows[:3] if isinstance(item, dict))
    return f"Studio deterministic preflight still has {len(rows)} issue(s)" + (f": {details}" if details else "")


def _repair_failure(
    result: RuntimeResult,
    *,
    message: str,
    repairs: int,
    preflight: dict[str, Any],
    failure_kind: RuntimeFailureKind,
    retryable: bool,
) -> RuntimeResult:
    metadata = dict(result.metadata or {})
    metadata.update(
        {
            "repair_attempts": repairs,
            "final_preflight": preflight,
            "failure_kind": failure_kind.value,
            "retryable": retryable,
        }
    )
    return replace(result, status="failed", returncode=2, message=message, metadata=metadata)


def _with_repair_metadata(
    result: RuntimeResult,
    *,
    status: str,
    repairs: int,
    preflight: dict[str, Any],
) -> RuntimeResult:
    metadata = dict(result.metadata or {})
    metadata.update({"repair_attempts": repairs, "final_preflight": preflight})
    return replace(result, status=status, metadata=metadata)


__all__ = ["run_pi_worker_repairs"]
