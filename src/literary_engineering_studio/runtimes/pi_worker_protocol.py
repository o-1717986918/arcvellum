"""Public event protocol projection for the embedded Pi Worker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKER_EVENTS = frozenset(
    {
        "runner.ready",
        "runner.execution.identity",
        "runner.strategy.bound",
        "runner.session.created",
        "runner.session.finished",
        "runner.session.status",
        "runner.provider.request.started",
        "runner.reasoning.started",
        "runner.reasoning.activity",
        "runner.reasoning.completed",
        "agent.message.delta",
        "agent.message.completed",
        "tool.started",
        "tool.completed",
        "tool.denied",
        "usage.updated",
        "file.changed",
        "runner.worker.result",
        "runner.conversation.result",
        "runner.warning",
    }
)


def public_event_data(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _public_value(item)
        for key, item in value.items()
        if not _secret_key(key)
    }


def last_worker_result(output_path: Path | None) -> dict[str, Any]:
    if output_path is None or not output_path.is_file():
        return {}
    result: dict[str, Any] = {}
    for line in output_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("event") != "runner.worker.result":
            continue
        data = payload.get("data")
        if isinstance(data, dict):
            result = public_event_data(data)
    return result


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return public_event_data(value)
    if isinstance(value, list):
        return [_public_value(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:20_000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2_000]


def _secret_key(value: object) -> bool:
    normalized = str(value).lower().replace("-", "_")
    return any(
        token in normalized
        for token in ("api_key", "apikey", "password", "secret", "credential", "auth")
    )


__all__ = ["WORKER_EVENTS", "last_worker_result", "public_event_data"]
