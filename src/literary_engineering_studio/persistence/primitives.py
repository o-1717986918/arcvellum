"""Stable schemas, validation, and serialization primitives for durable Studio storage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

JOB_SCHEMA = "literary-engineering-studio/worker-job/v0.3"

EVENT_SCHEMA = "literary-engineering-studio/run-event/v0.3"

EVENT_RETENTION_PER_JOB = 5000

DATABASE_SCHEMA_VERSION = 16

ACTIVE_STATUSES = {"queued", "running", "stopping"}

TERMINAL_STATUSES = {
    "complete",
    "failed",
    "cancelled",
    "runtime_failed",
    "blocked_by_core_gate",
    "blocked_empty_submission",
    "waiting_human",
    "waiting_host_agent",
    "route_ready",
}

def _validate_job_id(job_id: str) -> None:
    if not job_id.startswith("job-") or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in job_id):
        raise ValueError(f"invalid worker job id: {job_id}")

def _validate_advisor_id(session_id: str) -> None:
    if not session_id.startswith("advisor-") or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in session_id
    ):
        raise ValueError(f"invalid advisor session id: {session_id}")

def _validate_autopilot_id(run_id: str) -> None:
    if not run_id.startswith("autopilot-") or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in run_id
    ):
        raise ValueError(f"invalid autopilot run id: {run_id}")

def _validate_agent_session_id(session_id: str) -> str:
    value = str(session_id or "").strip()
    if not value or len(value) > 180 or any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError(f"invalid Agent session id: {session_id}")
    return value

def _public_request(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if "key" not in key.lower() and "secret" not in key.lower()}

def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_key(key: Any) -> bool:
    """Distinguish credentials from public token-usage telemetry.

    Token counts and budgets are ordinary numeric observability fields.  The
    former substring check redacted them together with bearer/API tokens,
    which made persisted usage events impossible to project back into typed
    read models.
    """

    normalized = str(key or "").strip().casefold().replace("-", "_")
    public_token_metrics = {
        "cache_read_tokens", "cache_write_tokens", "completion_tokens", "input_tokens",
        "max_output_tokens", "max_tokens", "output_tokens", "prompt_tokens",
        "reasoning_tokens", "token_budget", "token_count", "token_limit", "total_tokens",
    }
    if normalized in public_token_metrics:
        return False
    return any(
        marker in normalized
        for marker in ("api_key", "apikey", "credential", "password", "private_key", "secret", "token")
    ) or normalized == "authorization"

def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
