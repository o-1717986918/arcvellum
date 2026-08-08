"""Session lease contracts for role-isolated runtime reuse (AO-6, W6-7B).

Sessions may only be reused by the same role with identical project, model
and style identity, an un-invalidated Context Ledger epoch, a completed
previous task, and unspent token/time/failure budgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocols.violations import ContractViolation


class SessionRole(str, Enum):
    PLANNER = "planner"
    WRITER = "writer"
    REVIEWER = "reviewer"
    STATE_ANALYST = "state-analyst"
    ADVISOR_STEWARD = "advisor/steward"


@dataclass(frozen=True)
class SessionLease:
    session_id: str
    role: SessionRole
    project_id: str
    model_id: str
    style_mount_hash: str
    context_ledger_epoch: str
    previous_task_completed: bool
    token_used: int
    elapsed_seconds: float
    failure_count: int
    max_tokens: int
    max_seconds: float
    max_failures: int


@dataclass(frozen=True)
class SessionReuseDecision:
    reusable: bool
    reasons: tuple[str, ...]


SessionLeaseViolation = ContractViolation


def session_reusable(
    lease: SessionLease,
    *,
    role: SessionRole,
    project_id: str,
    model_id: str,
    style_mount_hash: str,
    context_ledger_epoch: str,
) -> SessionReuseDecision:
    """Decide whether an existing session may serve a new task."""
    reasons: list[str] = []
    if role != lease.role:
        reasons.append("role-mismatch")
    if project_id != lease.project_id:
        reasons.append("project-mismatch")
    if model_id != lease.model_id:
        reasons.append("model-mismatch")
    if style_mount_hash != lease.style_mount_hash:
        reasons.append("style-mismatch")
    if context_ledger_epoch != lease.context_ledger_epoch:
        reasons.append("context-ledger-invalidated")
    if not lease.previous_task_completed:
        reasons.append("previous-task-incomplete")
    if lease.token_used >= lease.max_tokens:
        reasons.append(
            "token-budget-exceeded"
            if lease.token_used > lease.max_tokens
            else "token-budget-exhausted"
        )
    if lease.elapsed_seconds >= lease.max_seconds:
        reasons.append(
            "time-budget-exceeded"
            if lease.elapsed_seconds > lease.max_seconds
            else "time-budget-exhausted"
        )
    if lease.failure_count >= lease.max_failures:
        reasons.append(
            "failure-budget-exceeded"
            if lease.failure_count > lease.max_failures
            else "failure-budget-exhausted"
        )
    return SessionReuseDecision(
        reusable=not reasons,
        reasons=tuple(reasons),
    )


def session_lease_violations(lease: SessionLease) -> tuple[SessionLeaseViolation, ...]:
    """Return deterministic structural violations for a session lease."""
    issues = _identity_violations(lease)
    issues.extend(_counter_violations(lease))
    issues.extend(_duration_violations(lease))
    issues.extend(_budget_limit_violations(lease))
    return tuple(issues)


def _identity_violations(lease: SessionLease) -> list[SessionLeaseViolation]:
    required = (
        ("session_id", "missing-session-id"),
        ("project_id", "missing-project-id"),
        ("model_id", "missing-model-id"),
    )
    return [
        SessionLeaseViolation(code=code, message=f"{name} must not be empty")
        for name, code in required
        if not getattr(lease, name)
    ]


def _counter_violations(lease: SessionLease) -> list[SessionLeaseViolation]:
    issues: list[SessionLeaseViolation] = []
    for name in ("token_used", "max_tokens", "failure_count", "max_failures"):
        value = getattr(lease, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(
                SessionLeaseViolation(
                    code="invalid-counter",
                    message=f"{name} must be a non-negative integer",
                )
            )
    return issues


def _duration_violations(lease: SessionLease) -> list[SessionLeaseViolation]:
    issues: list[SessionLeaseViolation] = []
    for name in ("elapsed_seconds", "max_seconds"):
        value = getattr(lease, name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            issues.append(
                SessionLeaseViolation(
                    code="invalid-duration",
                    message=f"{name} must be a non-negative number",
                )
            )
    return issues


def _budget_limit_violations(lease: SessionLease) -> list[SessionLeaseViolation]:
    issues: list[SessionLeaseViolation] = []
    for name in ("max_tokens", "max_seconds", "max_failures"):
        value = getattr(lease, name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value <= 0
        ):
            issues.append(
                SessionLeaseViolation(
                    code="invalid-budget-limit",
                    message=f"{name} must be greater than zero",
                )
            )
    return issues
