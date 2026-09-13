"""Controlled Project Agent actions backed by existing application services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ..application.failures import present_run
from .contracts import ProjectAgentActionDependencies


RecordDirection = Callable[..., dict[str, Any]]


def dependencies_from_actions(
    *,
    record_direction: RecordDirection,
    autopilot: Any,
) -> ProjectAgentActionDependencies:
    def save_direction(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        message = str(arguments.get("message") or "").strip()
        if not message:
            raise ValueError("project_record_direction requires a message")
        result = record_direction(root, message, actor="project-agent")
        record = result.get("record") if isinstance(result.get("record"), dict) else {}
        return {
            "ok": True,
            "operation": "record_direction",
            "record": record,
            "digest": str(result.get("digest") or ""),
            "receipt": _receipt("record_direction", record),
        }

    def control_creation(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments.get("operation") or "").strip().lower()
        if operation not in {"start", "pause", "resume"}:
            raise ValueError("creation_control operation must be start, pause, or resume")
        if operation == "start":
            run = autopilot.start(root)
        else:
            status = autopilot.status(root)
            active = status.get("run") if isinstance(status.get("run"), dict) else {}
            run_id = str(active.get("run_id") or "").strip()
            if not run_id:
                raise ValueError("creation_control requires an existing creation run")
            if operation == "pause":
                reason = str(arguments.get("reason") or "project-agent-user-request").strip()
                run = autopilot.pause(run_id, reason=reason[:500])
            else:
                # Full-auto authorization remains an explicit UI responsibility.
                run = autopilot.resume(run_id, authorized=False)
        presented = present_run(run)
        return {
            "ok": True,
            "operation": operation,
            "run": presented,
            "receipt": _receipt(f"creation_{operation}", presented),
        }

    return ProjectAgentActionDependencies(save_direction, control_creation)


def _receipt(operation: str, value: Mapping[str, Any]) -> dict[str, str]:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "operation": operation,
        "token": sha256(payload.encode("utf-8")).hexdigest()[:20],
    }


__all__ = ["dependencies_from_actions"]
