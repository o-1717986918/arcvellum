"""Append-only, content-minimizing audit records for capability calls."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contracts import CapabilityRequest, CapabilityResult


CAPABILITY_AUDIT_SCHEMA = "arcvellum/capability-audit-event/v1"
SENSITIVE_KEYS = ("token", "secret", "password", "credential", "api_key", "apikey", "authorization")


class CapabilityAuditWriter:
    def __init__(self, run_root: Path):
        self.path = run_root.resolve() / "capabilities" / "audit.jsonl"

    def record(self, request: CapabilityRequest, result: CapabilityResult) -> None:
        payload = {
            "schema": CAPABILITY_AUDIT_SCHEMA,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "request_id": request.request_id,
            "task_id": request.task_id,
            "capability_id": request.capability_id,
            "argument_summary": summarize_arguments(request.arguments),
            "status": result.status,
            "result_digest": result.result_digest,
            "duration_ms": result.duration_ms,
            "artifact": result.artifact,
            "truncated": result.truncated,
            "error_code": result.error_code,
        }
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, encoded)
        finally:
            os.close(descriptor)


def summarize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"keys": sorted(str(key) for key in arguments)}
    paths: list[str] = []
    categorical: dict[str, object] = {}
    redacted: list[str] = []
    digests: dict[str, dict[str, object]] = {}
    for raw_key, value in arguments.items():
        key = str(raw_key)
        kind, projected = _summarize_argument(key, value)
        if kind == "redacted":
            redacted.append(key)
        elif kind == "paths":
            paths.extend(projected)
        elif kind == "categorical":
            categorical[key] = projected
        else:
            digests[key] = projected
    if paths:
        summary["paths"] = paths
    if categorical:
        summary["categorical"] = categorical
    if digests:
        summary["value_digests"] = digests
    if redacted:
        summary["redacted_keys"] = sorted(redacted)
    return summary


def _summarize_argument(key: str, value: Any) -> tuple[str, Any]:
    lower = key.lower()
    if any(token in lower for token in SENSITIVE_KEYS):
        return "redacted", None
    if lower == "url":
        parsed = urlsplit(str(value))
        return "categorical", {
            "scheme": parsed.scheme,
            "host": parsed.hostname or "",
            "digest": _digest_text(str(value)),
        }
    if lower.endswith("path") and isinstance(value, str):
        return "paths", [value]
    if lower.endswith("paths") and isinstance(value, list):
        return "paths", [str(item) for item in value[:32]]
    if isinstance(value, (bool, int, float)) or value is None:
        return "categorical", value
    if isinstance(value, str):
        return "digest", {"chars": len(value), "sha256": _digest_text(value)}
    if isinstance(value, list):
        return "digest", {"items": len(value), "sha256": _digest_text(json.dumps(value, default=str))}
    return "digest", {"type": type(value).__name__}


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
