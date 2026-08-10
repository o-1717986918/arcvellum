"""Runtime-neutral execution policy projected from the formal task contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from ..contracts import TaskPackage
from .context_budget import (
    ContextRiskLevel,
    ContextTaskKind,
    classify_context_risk,
    classify_context_task,
)


PROFILE_SCHEMA = "arcvellum/task-execution-profile/v1"


class ExecutionProfileError(ValueError):
    """Raised when task semantics and its declared execution role conflict."""


@dataclass(frozen=True)
class ExecutionControl:
    name: str
    requested: object
    effective: object
    status: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "effective": self.effective,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TaskExecutionProfile:
    mode: str
    runtime_id: str
    task_kind: ContextTaskKind
    risk_level: ContextRiskLevel
    execution_policy: str
    agent_role: str
    controls: tuple[ExecutionControl, ...]
    digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": PROFILE_SCHEMA,
            "mode": self.mode,
            "runtime_id": self.runtime_id,
            "task_kind": self.task_kind.value,
            "risk_level": self.risk_level.value,
            "execution_policy": self.execution_policy,
            "agent_role": self.agent_role,
            "controls": {item.name: item.as_dict() for item in self.controls},
            "digest": self.digest,
        }

    def effective_int(self, name: str, fallback: int) -> int:
        control = next((item for item in self.controls if item.name == name), None)
        if control is None or control.effective is None:
            return fallback
        try:
            return int(control.effective)
        except (TypeError, ValueError):
            return fallback

    def effective_str(self, name: str, fallback: str) -> str:
        control = next((item for item in self.controls if item.name == name), None)
        if control is None or control.effective is None:
            return fallback
        value = str(control.effective).strip()
        return value or fallback

    def is_applied(self, name: str) -> bool:
        control = next((item for item in self.controls if item.name == name), None)
        return bool(control and control.status == "applied")


def resolve_task_execution_profile(
    task: TaskPackage,
    worker_config: Mapping[str, Any] | None = None,
    *,
    runtime_id: str,
    capability_ids: tuple[str, ...] | None = None,
) -> TaskExecutionProfile:
    worker = worker_config or {}
    kind = classify_context_task(task)
    risk = classify_context_risk(task, kind)
    _validate_role(task, kind)
    policy = task.execution_contract.execution_policy
    if policy == "deterministic":
        return _profile(task, runtime_id, kind, risk, "deterministic", _deterministic_controls())

    settings = _mapping(worker.get("execution_profile"))
    mode = _effective_mode(task, runtime_id, kind, settings)
    targets = _PROFILE_TARGETS[kind]
    capabilities = set(capability_ids or ())
    controls = (
        _control("total_timeout_seconds", targets, mode, int(worker.get("timeout_seconds") or 1800), True),
        _control(
            "max_repair_attempts",
            targets,
            mode,
            int(worker.get("max_repair_attempts") or 2),
            "bounded-repair" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
        _control(
            "first_event_timeout_seconds",
            targets,
            mode,
            None,
            "silence-timeout-control" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
        _control(
            "inter_event_timeout_seconds",
            targets,
            mode,
            None,
            "silence-timeout-control" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
        _control(
            "reasoning_policy",
            targets,
            mode,
            None,
            "reasoning-policy-control" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
        _control(
            "max_turns",
            targets,
            mode,
            None,
            "turn-limit-control" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
        _control(
            "max_tool_calls",
            targets,
            mode,
            None,
            "tool-limit-control" in capabilities,
            capabilities_known=capability_ids is not None,
        ),
    )
    return _profile(task, runtime_id, kind, risk, mode, controls)


def _targets(
    total: int,
    first: int,
    inter: int,
    reasoning: str,
    repairs: int,
    turns: int,
    tools: int,
) -> dict[str, object]:
    return {
        "total_timeout_seconds": total,
        "first_event_timeout_seconds": first,
        "inter_event_timeout_seconds": inter,
        "reasoning_policy": reasoning,
        "max_repair_attempts": repairs,
        "max_turns": turns,
        "max_tool_calls": tools,
    }


_PROFILE_TARGETS: dict[ContextTaskKind, dict[str, object]] = {
    ContextTaskKind.STRUCTURED: _targets(300, 90, 120, "minimal", 1, 2, 2),
    ContextTaskKind.CREATIVE: _targets(600, 180, 300, "medium", 1, 3, 4),
    ContextTaskKind.PLANNING: _targets(900, 240, 360, "medium", 1, 3, 4),
    ContextTaskKind.STYLE: _targets(600, 180, 300, "medium", 1, 3, 4),
    ContextTaskKind.ARCHAEOLOGY: _targets(600, 180, 300, "medium", 1, 3, 4),
    ContextTaskKind.PROSE: _targets(900, 240, 360, "medium", 1, 2, 2),
    ContextTaskKind.REVIEW: _targets(600, 240, 360, "high", 1, 2, 2),
}


def _effective_mode(
    task: TaskPackage,
    runtime_id: str,
    kind: ContextTaskKind,
    settings: Mapping[str, Any],
) -> str:
    requested = str(settings.get("mode") or "shadow").strip().lower()
    if requested == "off":
        return "off"
    rollout = _mapping(settings.get("enforcement"))
    if not bool(rollout.get("enabled")):
        return "shadow"
    selectors = {
        "runtimes": runtime_id,
        "routes": task.route,
        "states": task.current_state,
        "task_kinds": kind.value,
    }
    for key, value in selectors.items():
        allowed = _strings(rollout.get(key))
        if allowed and value not in allowed:
            return "shadow"
    return "enforced"


def _control(
    name: str,
    targets: Mapping[str, object],
    mode: str,
    legacy: object,
    supported: bool,
    *,
    capabilities_known: bool = True,
) -> ExecutionControl:
    requested = targets[name]
    if mode == "off":
        return ExecutionControl(name, requested, legacy, "disabled", "profile-disabled")
    if not capabilities_known:
        return ExecutionControl(name, requested, legacy, "pending", "runtime-capability-not-resolved")
    if not supported:
        return ExecutionControl(name, requested, legacy, "unsupported", "runtime-does-not-control-this-policy")
    if mode == "enforced":
        return ExecutionControl(name, requested, requested, "applied", "canary-policy-match")
    return ExecutionControl(name, requested, legacy, "shadow", "observed-without-behavior-change")


def _deterministic_controls() -> tuple[ExecutionControl, ...]:
    return tuple(
        ExecutionControl(name, value, value, "applied", "deterministic-engine")
        for name, value in _targets(0, 0, 0, "off", 0, 0, 0).items()
    )


def _profile(
    task: TaskPackage,
    runtime_id: str,
    kind: ContextTaskKind,
    risk: ContextRiskLevel,
    mode: str,
    controls: tuple[ExecutionControl, ...],
) -> TaskExecutionProfile:
    base = {
        "schema": PROFILE_SCHEMA,
        "mode": mode,
        "runtime_id": runtime_id,
        "task_kind": kind.value,
        "risk_level": risk.value,
        "execution_policy": task.execution_contract.execution_policy,
        "agent_role": task.execution_contract.agent_role,
        "controls": {item.name: item.as_dict() for item in controls},
    }
    digest = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return TaskExecutionProfile(
        mode=mode,
        runtime_id=runtime_id,
        task_kind=kind,
        risk_level=risk,
        execution_policy=task.execution_contract.execution_policy,
        agent_role=task.execution_contract.agent_role,
        controls=controls,
        digest=digest,
    )


def _validate_role(task: TaskPackage, kind: ContextTaskKind) -> None:
    if kind is ContextTaskKind.PROSE and task.execution_contract.agent_role != "main-creative-agent":
        raise ExecutionProfileError("prose tasks require agent_role=main-creative-agent")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> set[str]:
    return {str(item).strip() for item in value} if isinstance(value, (list, tuple)) else set()
