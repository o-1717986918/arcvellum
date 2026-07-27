"""Deterministic first-turn context budgets for formal Agent tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

from ..contracts import TaskPackage


LEGACY_MAX_INLINE_CHARACTERS = 180_000


class ContextBudgetMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    BOUNDED = "bounded"


class ContextTaskKind(str, Enum):
    PROSE = "prose"
    REVIEW = "review"
    ARCHAEOLOGY = "archaeology"
    STYLE = "style"
    PLANNING = "planning"
    CREATIVE = "creative"
    STRUCTURED = "structured"


class ContextRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_INLINE_LIMITS = {
    ContextTaskKind.PROSE: 78_000,
    ContextTaskKind.REVIEW: 55_000,
    ContextTaskKind.ARCHAEOLOGY: 45_000,
    ContextTaskKind.STYLE: 50_000,
    ContextTaskKind.PLANNING: 45_000,
    ContextTaskKind.CREATIVE: 55_000,
    ContextTaskKind.STRUCTURED: 24_000,
}
_RISK_MULTIPLIERS = {
    ContextRiskLevel.LOW: 0.85,
    ContextRiskLevel.MEDIUM: 1.0,
    ContextRiskLevel.HIGH: 1.15,
}


@dataclass(frozen=True)
class TaskContextBudget:
    mode: ContextBudgetMode
    task_kind: ContextTaskKind
    role: str
    risk_level: ContextRiskLevel
    target_inline_characters: int
    enforced_inline_characters: int
    max_exact_on_demand_characters: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "arcvellum/task-context-budget/v1",
            **asdict(self),
            "mode": self.mode.value,
            "task_kind": self.task_kind.value,
            "risk_level": self.risk_level.value,
        }


@dataclass(frozen=True)
class ContextBudgetReport:
    mode: ContextBudgetMode
    task_kind: ContextTaskKind
    role: str
    risk_level: ContextRiskLevel
    target_inline_characters: int
    enforced_inline_characters: int
    first_turn_visible_characters: int
    exact_on_demand_characters: int
    excluded_characters: int
    authorized_characters: int
    mandatory_characters: int
    included_file_count: int
    on_demand_file_count: int
    excluded_file_count: int
    budget_overage_count: int
    budget_overage_characters: int
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "arcvellum/context-budget-report/v1",
            **asdict(self),
            "mode": self.mode.value,
            "task_kind": self.task_kind.value,
            "risk_level": self.risk_level.value,
        }


class ContextBudgetExceeded(RuntimeError):
    """Raised when bounded mode cannot preserve all mandatory context."""


def resolve_task_context_budget(
    task: TaskPackage,
    worker_config: Mapping[str, Any] | None = None,
) -> TaskContextBudget:
    config = _mapping((worker_config or {}).get("context_budget"))
    mode = _mode(config.get("mode"))
    kind = _task_kind(task)
    role = task.execution_contract.agent_role
    risk = _risk_level(task, kind)
    configured_limits = _mapping(config.get("inline_limits"))
    base = _positive_int(configured_limits.get(kind.value), _INLINE_LIMITS[kind])
    target = int(round(base * _RISK_MULTIPLIERS[risk]))
    target = max(24_000, min(target, LEGACY_MAX_INLINE_CHARACTERS))
    legacy = _positive_int(
        config.get("legacy_max_inline_characters"),
        LEGACY_MAX_INLINE_CHARACTERS,
    )
    enforced = target if mode is ContextBudgetMode.BOUNDED else legacy
    on_demand = _positive_int(config.get("max_exact_on_demand_characters"), target * 3)
    return TaskContextBudget(
        mode=mode,
        task_kind=kind,
        role=role,
        risk_level=risk,
        target_inline_characters=target,
        enforced_inline_characters=enforced,
        max_exact_on_demand_characters=on_demand,
    )


def build_context_budget_report(
    budget: TaskContextBudget,
    *,
    first_turn_visible_characters: int,
    exact_on_demand_characters: int,
    excluded_characters: int,
    authorized_characters: int,
    mandatory_characters: int,
    included_file_count: int,
    on_demand_file_count: int,
    excluded_file_count: int,
) -> ContextBudgetReport:
    overage = max(0, first_turn_visible_characters - budget.target_inline_characters)
    payload = {
        "mode": budget.mode.value,
        "task_kind": budget.task_kind.value,
        "role": budget.role,
        "risk_level": budget.risk_level.value,
        "target_inline_characters": budget.target_inline_characters,
        "enforced_inline_characters": budget.enforced_inline_characters,
        "first_turn_visible_characters": max(0, first_turn_visible_characters),
        "exact_on_demand_characters": max(0, exact_on_demand_characters),
        "excluded_characters": max(0, excluded_characters),
        "authorized_characters": max(0, authorized_characters),
        "mandatory_characters": max(0, mandatory_characters),
        "included_file_count": max(0, included_file_count),
        "on_demand_file_count": max(0, on_demand_file_count),
        "excluded_file_count": max(0, excluded_file_count),
        "budget_overage_count": int(overage > 0),
        "budget_overage_characters": overage,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ContextBudgetReport(
        mode=budget.mode,
        task_kind=budget.task_kind,
        role=budget.role,
        risk_level=budget.risk_level,
        target_inline_characters=budget.target_inline_characters,
        enforced_inline_characters=budget.enforced_inline_characters,
        first_turn_visible_characters=payload["first_turn_visible_characters"],
        exact_on_demand_characters=payload["exact_on_demand_characters"],
        excluded_characters=payload["excluded_characters"],
        authorized_characters=payload["authorized_characters"],
        mandatory_characters=payload["mandatory_characters"],
        included_file_count=payload["included_file_count"],
        on_demand_file_count=payload["on_demand_file_count"],
        excluded_file_count=payload["excluded_file_count"],
        budget_overage_count=payload["budget_overage_count"],
        budget_overage_characters=payload["budget_overage_characters"],
        digest=digest,
    )


def _task_kind(task: TaskPackage) -> ContextTaskKind:
    task_type = task.task_type.lower()
    route = task.route.lower()
    state = task.current_state.lower()
    role = task.execution_contract.agent_role.lower()
    haystack = " ".join((task_type, route, state, task.task_id.lower()))
    if "prose" in task_type or "generation-agent-task" in state:
        return ContextTaskKind.PROSE
    route_kind = _route_task_kind(route, haystack)
    if route_kind is not None:
        return route_kind
    scene_kind = _scene_task_kind(state)
    if scene_kind is not None:
        return scene_kind
    if "review" in task_type or "review" in state:
        return ContextTaskKind.REVIEW
    if "creative" in role:
        return ContextTaskKind.CREATIVE
    if "review" in role:
        return ContextTaskKind.REVIEW
    return ContextTaskKind.STRUCTURED


def _route_task_kind(
    route: str,
    haystack: str,
) -> ContextTaskKind | None:
    if route == "source-ingest" or "archaeology" in haystack:
        return ContextTaskKind.ARCHAEOLOGY
    if route == "style-learning" or "style" in haystack:
        return ContextTaskKind.STYLE
    if route in {"longform-planning", "project-initialization"} or "planning" in haystack:
        return ContextTaskKind.PLANNING
    return None


def _scene_task_kind(state: str) -> ContextTaskKind | None:
    if any(token in state for token in ("roleplay", "branch", "composition")):
        return ContextTaskKind.CREATIVE
    if any(token in state for token in ("state-", "canon-", "continuity-ledger")):
        return ContextTaskKind.STRUCTURED
    return None


def _risk_level(task: TaskPackage, kind: ContextTaskKind) -> ContextRiskLevel:
    scene_policy = task.payload.get("creative_scene_policy")
    if isinstance(scene_policy, dict):
        explicit = str(scene_policy.get("risk_level") or "").strip().lower()
        if explicit in {item.value for item in ContextRiskLevel}:
            return ContextRiskLevel(explicit)
    if kind in {
        ContextTaskKind.PROSE,
        ContextTaskKind.REVIEW,
        ContextTaskKind.ARCHAEOLOGY,
    }:
        return ContextRiskLevel.HIGH
    high_impact = any(
        path.startswith(("canon/", "characters/", "drafts/scenes/", "manuscript/"))
        for path in task.expected_outputs
    )
    if high_impact or kind in {ContextTaskKind.STYLE, ContextTaskKind.CREATIVE}:
        return ContextRiskLevel.MEDIUM
    return ContextRiskLevel.LOW


def _mode(value: object) -> ContextBudgetMode:
    normalized = str(value or ContextBudgetMode.SHADOW.value).strip().lower()
    try:
        return ContextBudgetMode(normalized)
    except ValueError:
        return ContextBudgetMode.SHADOW


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
