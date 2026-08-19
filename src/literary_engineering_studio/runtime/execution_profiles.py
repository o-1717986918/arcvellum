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
from .reasoning_policy import ReasoningBudget, resolve_reasoning_budget


PROFILE_SCHEMA = "arcvellum/task-execution-profile/v2"
PROFILE_SCHEMA_V1 = "arcvellum/task-execution-profile/v1"


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
    reasoning_budget: ReasoningBudget
    reasoning_budget_status: str
    reasoning_budget_provider_support: str
    digest: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": PROFILE_SCHEMA,
            "compatible_with": [PROFILE_SCHEMA_V1],
            "mode": self.mode,
            "runtime_id": self.runtime_id,
            "task_kind": self.task_kind.value,
            "risk_level": self.risk_level.value,
            "execution_policy": self.execution_policy,
            "agent_role": self.agent_role,
            "controls": {item.name: item.as_dict() for item in self.controls},
            "reasoning_budget": {
                "requested": self.reasoning_budget.as_dict(),
                "effective": (
                    self.reasoning_budget.as_dict()
                    if self.reasoning_budget_status == "applied"
                    else None
                ),
                "status": self.reasoning_budget_status,
                "provider_support": self.reasoning_budget_provider_support,
            },
            "digest": self.digest,
        }

    def safe_projection_v1(self) -> dict[str, object]:
        """Compatibility projection for readers that only understand Profile v1."""

        return {
            "schema": PROFILE_SCHEMA_V1,
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
    settings = _mapping(worker.get("execution_profile"))
    budget_settings = _mapping(settings.get("reasoning_budget"))
    budget = _resolve_budget(kind, policy, budget_settings)
    if policy == "deterministic":
        return _profile(
            task,
            runtime_id,
            kind,
            risk,
            "deterministic",
            _deterministic_controls(),
            budget,
            "applied",
            "not-applicable",
        )

    mode = _effective_mode(task, runtime_id, kind, settings)
    capabilities = set(capability_ids or ())
    controls = _agent_controls(
        task,
        kind,
        worker,
        mode,
        capabilities,
        capabilities_known=capability_ids is not None,
    )
    budget_status, provider_support = _reasoning_budget_status(
        budget_settings,
        mode,
        capability_ids,
        capabilities,
    )
    return _profile(
        task,
        runtime_id,
        kind,
        risk,
        mode,
        controls,
        budget,
        budget_status,
        provider_support,
    )


def _resolve_budget(
    kind: ContextTaskKind,
    policy: str,
    settings: Mapping[str, Any],
) -> ReasoningBudget:
    return resolve_reasoning_budget(
        kind,
        policy,
        max_escalations=_optional_int(settings.get("max_escalations")),
    )


def _agent_controls(
    task: TaskPackage,
    kind: ContextTaskKind,
    worker: Mapping[str, Any],
    mode: str,
    capabilities: set[str],
    *,
    capabilities_known: bool,
) -> tuple[ExecutionControl, ...]:
    targets = dict(_PROFILE_TARGETS[kind])
    targets["max_tool_calls"] = max(
        int(targets["max_tool_calls"]),
        _minimum_bounded_worker_tool_calls(task),
    )
    legacy = {
        "total_timeout_seconds": int(worker.get("timeout_seconds") or 1800),
        "max_repair_attempts": int(worker.get("max_repair_attempts") or 2),
    }
    support = {
        "total_timeout_seconds": True,
        "max_repair_attempts": "bounded-repair" in capabilities,
        "first_event_timeout_seconds": "silence-timeout-control" in capabilities,
        "inter_event_timeout_seconds": "silence-timeout-control" in capabilities,
        "reasoning_policy": "reasoning-policy-control" in capabilities,
        "max_turns": "turn-limit-control" in capabilities,
        "max_tool_calls": "tool-limit-control" in capabilities,
    }
    return tuple(
        _control(
            name,
            targets,
            mode,
            legacy.get(name),
            supported,
            capabilities_known=(True if name == "total_timeout_seconds" else capabilities_known),
        )
        for name, supported in support.items()
    )


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
    ContextTaskKind.STRUCTURED: _targets(300, 90, 120, "minimal", 1, 4, 2),
    ContextTaskKind.CREATIVE: _targets(600, 180, 300, "medium", 1, 5, 4),
    ContextTaskKind.PLANNING: _targets(900, 240, 360, "medium", 1, 5, 4),
    ContextTaskKind.STYLE: _targets(600, 180, 300, "medium", 1, 5, 4),
    ContextTaskKind.ARCHAEOLOGY: _targets(600, 180, 300, "medium", 1, 5, 4),
    ContextTaskKind.PROSE: _targets(1200, 240, 360, "minimal", 8, 6, 8),
    ContextTaskKind.REVIEW: _targets(600, 240, 360, "high", 1, 5, 2),
}


def _minimum_bounded_worker_tool_calls(task: TaskPackage) -> int:
    """Reserve writes plus context, validation, and completion for narrow workers."""

    agent_outputs = sum(
        output.kind not in {"completion-evidence", "deterministic", "human-approval"}
        for output in task.execution_contract.outputs
    )
    return max(1, agent_outputs + 4)


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
    reasoning_budget: ReasoningBudget,
    reasoning_budget_status: str,
    reasoning_budget_provider_support: str,
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
        "reasoning_budget": {
            "requested": reasoning_budget.as_dict(),
            "effective": reasoning_budget.as_dict() if reasoning_budget_status == "applied" else None,
            "status": reasoning_budget_status,
            "provider_support": reasoning_budget_provider_support,
        },
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
        reasoning_budget=reasoning_budget,
        reasoning_budget_status=reasoning_budget_status,
        reasoning_budget_provider_support=reasoning_budget_provider_support,
        digest=digest,
    )


def _reasoning_budget_status(
    settings: Mapping[str, Any],
    mode: str,
    capability_ids: tuple[str, ...] | None,
    capabilities: set[str],
) -> tuple[str, str]:
    if not bool(settings.get("enabled", True)) or mode == "off":
        return "disabled", "unknown"
    if capability_ids is None:
        return "pending", "unknown"
    if "reasoning-budget-control" not in capabilities:
        return "shadow", "unsupported"
    # Adapter support is known here; provider support remains unknown until receipt.
    return ("applied" if mode == "enforced" else "shadow"), "unknown"


def _validate_role(task: TaskPackage, kind: ContextTaskKind) -> None:
    if kind is ContextTaskKind.PROSE and task.execution_contract.agent_role != "main-creative-agent":
        raise ExecutionProfileError("prose tasks require agent_role=main-creative-agent")


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> set[str]:
    return {str(item).strip() for item in value} if isinstance(value, (list, tuple)) else set()


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None
