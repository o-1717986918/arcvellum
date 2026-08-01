"""Bounded replan budget contracts for AO-7 (W6-8B).

Replanning is limited per scope by the Freedom Budget; once the budget is
exhausted the campaign must stop or fall back instead of looping forever.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import ReplanTrigger


@dataclass(frozen=True)
class ReplanBudgetState:
    scope_key: str
    replan_count: int = 0
    max_replans: int = 2


@dataclass(frozen=True)
class ReplanDecision:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReplanBudgetViolation:
    code: str
    message: str


def replan_allowed(
    state: ReplanBudgetState,
    *,
    trigger: ReplanTrigger,
) -> ReplanDecision:
    """A replan is allowed only while the per-scope budget remains."""
    reasons: list[str] = []
    if state.replan_count >= state.max_replans:
        reasons.append("replan-budget-exhausted")
    if trigger is ReplanTrigger.USER_DIRECTION_CHANGED and state.replan_count > 0:
        reasons.append("user-direction-replan-limited")
    return ReplanDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
    )


def replan_budget_violations(
    state: ReplanBudgetState,
) -> tuple[ReplanBudgetViolation, ...]:
    """Return deterministic structural violations for replan budget state."""
    issues: list[ReplanBudgetViolation] = []
    if not state.scope_key:
        issues.append(
            ReplanBudgetViolation(
                code="missing-scope-key",
                message="scope_key must not be empty",
            )
        )
    if not isinstance(state.replan_count, int) or state.replan_count < 0:
        issues.append(
            ReplanBudgetViolation(
                code="invalid-replan-count",
                message="replan_count must be a non-negative integer",
            )
        )
    if not isinstance(state.max_replans, int) or state.max_replans < 1:
        issues.append(
            ReplanBudgetViolation(
                code="invalid-max-replans",
                message="max_replans must be a positive integer",
            )
        )
    return tuple(issues)
