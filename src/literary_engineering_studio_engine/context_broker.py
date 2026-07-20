"""Context trace helpers for formal scene routes.

The context packet is the readable summary; the context trace is the audit
record that proves which files and context groups fed that summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTEXT_TRACE_SCHEMA = "literary-engineering-workbench/context-trace/v1"


@dataclass(frozen=True)
class ContextTraceValidation:
    path: Path
    status: str
    message: str
    payload: dict[str, Any]

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def default_context_trace_path(context_path: Path) -> Path:
    """Return the sidecar trace path for a context packet."""

    return context_path.with_suffix(".trace.json")


def write_context_trace(path: Path, payload: dict[str, Any]) -> Path:
    """Write a context trace payload with the stable schema marker."""

    path.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(payload)
    clean.setdefault("schema", CONTEXT_TRACE_SCHEMA)
    clean.setdefault("created_at", _now())
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def context_trace_status(root: Path, scene_id: str, context_path: Path | None = None) -> ContextTraceValidation:
    """Validate the formal context trace expected for a scene."""

    context = context_path or root / "memory" / "context_packets" / f"{scene_id}.md"
    trace = default_context_trace_path(context)
    rel_trace = _rel(trace, root)
    if not trace.exists():
        return ContextTraceValidation(trace, "missing", f"missing context trace: {rel_trace}", {})
    try:
        payload = json.loads(trace.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ContextTraceValidation(trace, "invalid", f"invalid context trace JSON: {rel_trace}: {exc}", {})
    if not isinstance(payload, dict):
        return ContextTraceValidation(trace, "invalid", f"context trace root is not object: {rel_trace}", {})
    if payload.get("schema") != CONTEXT_TRACE_SCHEMA:
        return ContextTraceValidation(trace, "invalid", f"context trace schema mismatch: {payload.get('schema') or 'missing'}", payload)
    if str(payload.get("scene_id") or "") != scene_id:
        return ContextTraceValidation(trace, "invalid", f"context trace scene_id mismatch: expected {scene_id}", payload)
    expected_context = _rel(context, root)
    recorded_context = str(payload.get("context_packet") or "").replace("\\", "/").lstrip("./")
    if recorded_context and recorded_context != expected_context:
        return ContextTraceValidation(trace, "invalid", f"context trace points to {recorded_context}, expected {expected_context}", payload)
    missing_required = payload.get("missing_required_context")
    if isinstance(missing_required, list) and missing_required:
        return ContextTraceValidation(trace, "incomplete", f"context trace has missing required context: {', '.join(str(item) for item in missing_required)}", payload)
    loaded_files = payload.get("loaded_files")
    if not isinstance(loaded_files, list) or not loaded_files:
        return ContextTraceValidation(trace, "invalid", "context trace loaded_files is empty or missing", payload)
    return ContextTraceValidation(trace, "pass", f"context trace valid: {rel_trace}", payload)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
