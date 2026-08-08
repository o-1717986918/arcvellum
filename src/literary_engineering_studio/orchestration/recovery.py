"""Deterministic recovery ladder for AO-7 unattended campaigns (W6-8B).

Every failure class maps to a fixed, bounded escalation ladder.  The ladder
never masks a blocker: it ends in ``stop-with-evidence`` instead of retrying
forever or silently changing the plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocols.violations import ContractViolation


class RecoveryStep(str, Enum):
    RETRY = "retry"
    SESSION_RENEW = "session-renew"
    CHECKPOINT_RESTORE = "checkpoint-restore"
    BOUNDED_REPLAN = "bounded-replan"
    STOP_WITH_EVIDENCE = "stop-with-evidence"


_LADDER: dict[str, tuple[RecoveryStep, ...]] = {
    "provider_unavailable": (
        RecoveryStep.RETRY,
        RecoveryStep.RETRY,
        RecoveryStep.SESSION_RENEW,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "process_crash": (
        RecoveryStep.CHECKPOINT_RESTORE,
        RecoveryStep.BOUNDED_REPLAN,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "transient_network": (
        RecoveryStep.RETRY,
        RecoveryStep.SESSION_RENEW,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "first_event_timeout": (
        RecoveryStep.RETRY,
        RecoveryStep.SESSION_RENEW,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "idle_timeout": (
        RecoveryStep.RETRY,
        RecoveryStep.SESSION_RENEW,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "total_timeout": (
        RecoveryStep.RETRY,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "provider_quota": (RecoveryStep.STOP_WITH_EVIDENCE,),
    "authentication_failure": (RecoveryStep.STOP_WITH_EVIDENCE,),
    "model_error": (RecoveryStep.STOP_WITH_EVIDENCE,),
    "validation_failure": (
        RecoveryStep.CHECKPOINT_RESTORE,
        RecoveryStep.BOUNDED_REPLAN,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "writeback_failure": (
        RecoveryStep.CHECKPOINT_RESTORE,
        RecoveryStep.BOUNDED_REPLAN,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "authorization_expired": (
        RecoveryStep.SESSION_RENEW,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "version_conflict": (
        RecoveryStep.CHECKPOINT_RESTORE,
        RecoveryStep.BOUNDED_REPLAN,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "no_progress": (
        RecoveryStep.BOUNDED_REPLAN,
        RecoveryStep.STOP_WITH_EVIDENCE,
    ),
    "budget_exhausted": (RecoveryStep.STOP_WITH_EVIDENCE,),
}


@dataclass(frozen=True)
class RecoveryDecision:
    step: RecoveryStep
    reasons: tuple[str, ...]


RecoveryViolation = ContractViolation


def recovery_step(
    failure_code: str,
    attempt: int,
) -> RecoveryDecision:
    """Return the deterministic recovery step for a failure class."""
    if attempt < 1:
        return RecoveryDecision(
            step=RecoveryStep.STOP_WITH_EVIDENCE,
            reasons=("invalid-attempt",),
        )
    ladder = _LADDER.get(failure_code)
    if ladder is None:
        return RecoveryDecision(
            step=RecoveryStep.STOP_WITH_EVIDENCE,
            reasons=("unknown-failure-class",),
        )
    if attempt > len(ladder):
        return RecoveryDecision(
            step=RecoveryStep.STOP_WITH_EVIDENCE,
            reasons=("ladder-exhausted",),
        )
    return RecoveryDecision(
        step=ladder[attempt - 1],
        reasons=(),
    )


def recovery_violations(failure_code: str, attempt: int) -> tuple[RecoveryViolation, ...]:
    """Return deterministic violations for a recovery request."""
    issues: list[RecoveryViolation] = []
    if not failure_code:
        issues.append(
            RecoveryViolation(
                code="missing-failure-code",
                message="failure_code must not be empty",
            )
        )
    if not isinstance(attempt, int) or attempt < 1:
        issues.append(
            RecoveryViolation(
                code="invalid-attempt",
                message="attempt must be a positive integer",
            )
        )
    return tuple(issues)
