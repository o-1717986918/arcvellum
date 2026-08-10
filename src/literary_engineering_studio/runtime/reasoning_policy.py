"""Pure reasoning-budget recommendations and retry decisions.

This module owns policy only. Runtime capability detection and provider execution
remain in the runtime adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .context_budget import ContextTaskKind


_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")


class ReasoningAction(str, Enum):
    KEEP = "keep"
    ESCALATE = "escalate"
    RETRY_SAME = "retry_same"
    STOP = "stop"


@dataclass(frozen=True)
class ReasoningBudget:
    initial_level: str
    maximum_level: str
    per_request_tokens: int
    total_tokens: int
    max_provider_requests: int
    max_escalations: int
    escalation_triggers: tuple[str, ...]
    over_budget_action: str

    def as_dict(self) -> dict[str, object]:
        return {
            "initial_level": self.initial_level,
            "maximum_level": self.maximum_level,
            "per_request_tokens": self.per_request_tokens,
            "total_tokens": self.total_tokens,
            "max_provider_requests": self.max_provider_requests,
            "max_escalations": self.max_escalations,
            "escalation_triggers": list(self.escalation_triggers),
            "over_budget_action": self.over_budget_action,
        }


@dataclass(frozen=True)
class ReasoningUsage:
    reasoning_tokens: int = 0
    provider_requests: int = 0
    escalations: int = 0


@dataclass(frozen=True)
class ReasoningDecision:
    action: ReasoningAction
    level: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {
            "action": self.action.value,
            "level": self.level,
            "reason": self.reason,
        }


_ESCALATION_TRIGGERS = (
    "canon_scene_conflict",
    "high_trust_evidence_conflict",
    "global_planning_obligation",
    "semantic_literary_judgment",
    "first_semantic_preflight_failure",
)

_MECHANICAL_ISSUES = frozenset(
    {
        "invalid_json",
        "invalid_yaml",
        "schema_error",
        "missing_field",
        "missing_path",
        "missing_output",
        "completion_missing",
        "duplicate_validation",
        "word_count",
        "style_lint",
    }
)
_TERMINAL_ISSUES = frozenset(
    {
        "no_progress",
        "provider_error",
        "provider_quota",
        "authentication_failure",
        "network_error",
        "timeout",
    }
)
_SEMANTIC_ISSUES = frozenset(
    {
        "canon_conflict",
        "evidence_conflict",
        "global_obligation",
        "character_logic",
        "narrative_rhythm",
        "promise_payoff",
        "semantic_preflight",
    }
)


def _budget(
    initial: str,
    maximum: str,
    per_request: int,
    total: int,
    requests: int,
) -> ReasoningBudget:
    return ReasoningBudget(
        initial_level=initial,
        maximum_level=maximum,
        per_request_tokens=per_request,
        total_tokens=total,
        max_provider_requests=requests,
        max_escalations=1,
        escalation_triggers=_ESCALATION_TRIGGERS,
        over_budget_action="validate_then_stop",
    )


_BUDGETS = {
    ContextTaskKind.STRUCTURED: _budget("minimal", "low", 256, 768, 3),
    ContextTaskKind.CREATIVE: _budget("low", "medium", 512, 2_048, 4),
    ContextTaskKind.PLANNING: _budget("low", "medium", 768, 4_096, 4),
    ContextTaskKind.STYLE: _budget("low", "medium", 768, 3_072, 4),
    ContextTaskKind.ARCHAEOLOGY: _budget("low", "medium", 512, 2_048, 4),
    ContextTaskKind.PROSE: _budget("minimal", "low", 512, 2_048, 3),
    ContextTaskKind.REVIEW: _budget("low", "medium", 768, 3_072, 4),
}


def resolve_reasoning_budget(
    task_kind: ContextTaskKind,
    execution_policy: str,
    *,
    max_escalations: int | None = None,
) -> ReasoningBudget:
    if execution_policy == "deterministic":
        return ReasoningBudget("off", "off", 0, 0, 0, 0, (), "stop")
    base = _BUDGETS[task_kind]
    if max_escalations is None:
        return base
    bounded = min(base.max_escalations, max(0, int(max_escalations)))
    return ReasoningBudget(
        initial_level=base.initial_level,
        maximum_level=base.maximum_level,
        per_request_tokens=base.per_request_tokens,
        total_tokens=base.total_tokens,
        max_provider_requests=base.max_provider_requests,
        max_escalations=bounded,
        escalation_triggers=base.escalation_triggers,
        over_budget_action=base.over_budget_action,
    )


def decide_reasoning_action(
    budget: ReasoningBudget,
    *,
    current_level: str,
    attempt: int,
    issue_categories: Iterable[str] = (),
    evidence_conflict: bool = False,
    usage: ReasoningUsage = ReasoningUsage(),
    repeated_progress_fingerprint: bool = False,
) -> ReasoningDecision:
    """Return a deterministic recommendation without invoking a model."""

    level = _normalized_level(current_level, budget.initial_level)
    issues = {_normalize_issue(item) for item in issue_categories if str(item).strip()}
    if budget.maximum_level == "off":
        return ReasoningDecision(ReasoningAction.STOP, "off", "deterministic-task")
    if usage.reasoning_tokens >= budget.total_tokens:
        return ReasoningDecision(ReasoningAction.STOP, level, "reasoning-token-budget-exhausted")
    if usage.provider_requests >= budget.max_provider_requests:
        return ReasoningDecision(ReasoningAction.STOP, level, "provider-request-budget-exhausted")
    if repeated_progress_fingerprint and attempt >= 2:
        return ReasoningDecision(ReasoningAction.STOP, level, "same-progress-fingerprint-repeated")
    if issues & _TERMINAL_ISSUES:
        return ReasoningDecision(ReasoningAction.STOP, level, "non-reasoning-runtime-failure")
    if issues & _MECHANICAL_ISSUES:
        return ReasoningDecision(ReasoningAction.RETRY_SAME, level, "mechanical-repair-required")
    semantic = evidence_conflict or bool(issues & _SEMANTIC_ISSUES)
    can_escalate = (
        semantic
        and attempt <= 1
        and usage.escalations < budget.max_escalations
        and _level_index(level) < _level_index(budget.maximum_level)
    )
    if can_escalate:
        return ReasoningDecision(
            ReasoningAction.ESCALATE,
            _next_level(level, budget.maximum_level),
            "semantic-uncertainty-allows-one-step-escalation",
        )
    return ReasoningDecision(ReasoningAction.KEEP, level, "current-budget-is-sufficient")


def _normalize_issue(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _normalized_level(value: str, fallback: str) -> str:
    normalized = str(value).strip().lower()
    return normalized if normalized in _LEVELS else fallback


def _level_index(value: str) -> int:
    return _LEVELS.index(_normalized_level(value, "off"))


def _next_level(current: str, maximum: str) -> str:
    return _LEVELS[min(_level_index(current) + 1, _level_index(maximum))]


__all__ = [
    "ReasoningAction",
    "ReasoningBudget",
    "ReasoningDecision",
    "ReasoningUsage",
    "decide_reasoning_action",
    "resolve_reasoning_budget",
]
