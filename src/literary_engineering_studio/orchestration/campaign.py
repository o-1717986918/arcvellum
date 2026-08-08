"""Unattended Campaign contracts for AO-7 (W6-8C).

A campaign may advance autonomously only within its policy bounds.  Any
pending pause reason stops the campaign with evidence; unhandled reasons
fail closed instead of being ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class CampaignPauseReason(str, Enum):
    HUMAN_DECISION = "human-decision"
    APPROVAL = "approval"
    RELEASE_GATE = "release-gate"
    NO_PROGRESS = "no-progress"
    RECOVERY_EXHAUSTED = "recovery-exhausted"
    BUDGET_EXHAUSTED = "budget-exhausted"
    USER_DIRECTION = "user-direction"


@dataclass(frozen=True)
class CampaignPolicy:
    scope_kind: Literal["chapter", "book"]
    scope_key: str
    max_autonomous_steps: int
    checkpoint_interval_steps: int
    pause_on: tuple[CampaignPauseReason, ...]


@dataclass(frozen=True)
class CampaignState:
    scope_key: str
    completed_steps: int = 0
    last_checkpoint_step: int = 0
    pending_pause_reasons: tuple[CampaignPauseReason, ...] = ()


@dataclass(frozen=True)
class CampaignStepDecision:
    proceed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CampaignViolation:
    code: str
    message: str


def campaign_step_allowed(
    state: CampaignState,
    policy: CampaignPolicy,
) -> CampaignStepDecision:
    """A campaign step proceeds only inside policy bounds."""
    reasons: list[str] = []
    if state.pending_pause_reasons:
        unhandled = [
            reason.value
            for reason in state.pending_pause_reasons
            if reason not in policy.pause_on
        ]
        if unhandled:
            reasons.append(f"unhandled-pause-reason:{unhandled[0]}")
        else:
            reasons.append(
                f"pause:{state.pending_pause_reasons[0].value}"
            )
    if state.completed_steps >= policy.max_autonomous_steps:
        reasons.append("max-autonomous-steps")
    return CampaignStepDecision(
        proceed=not reasons,
        reasons=tuple(reasons),
    )


def checkpoint_due(
    state: CampaignState,
    policy: CampaignPolicy,
) -> bool:
    """Return whether enough new steps elapsed since the last checkpoint."""
    if policy.checkpoint_interval_steps < 1:
        return False
    progress_since_checkpoint = (
        state.completed_steps - state.last_checkpoint_step
    )
    return progress_since_checkpoint >= policy.checkpoint_interval_steps


def campaign_violations(
    state: CampaignState,
    policy: CampaignPolicy,
) -> tuple[CampaignViolation, ...]:
    """Return deterministic structural violations for campaign inputs."""
    issues: list[CampaignViolation] = []
    if state.scope_key != policy.scope_key:
        issues.append(
            CampaignViolation(
                code="scope-mismatch",
                message="campaign state and policy must share scope_key",
            )
        )
    if not state.scope_key:
        issues.append(
            CampaignViolation(
                code="missing-scope-key",
                message="scope_key must not be empty",
            )
        )
    if policy.scope_kind not in {"chapter", "book"}:
        issues.append(
            CampaignViolation(
                code="invalid-scope-kind",
                message="scope_kind must be chapter or book",
            )
        )
    if not isinstance(state.completed_steps, int) or state.completed_steps < 0:
        issues.append(
            CampaignViolation(
                code="invalid-completed-steps",
                message="completed_steps must be a non-negative integer",
            )
        )
    if not isinstance(state.last_checkpoint_step, int) or state.last_checkpoint_step < 0:
        issues.append(
            CampaignViolation(
                code="invalid-checkpoint-step",
                message="last_checkpoint_step must be a non-negative integer",
            )
        )
    elif state.last_checkpoint_step > state.completed_steps:
        issues.append(
            CampaignViolation(
                code="checkpoint-ahead-of-progress",
                message="last_checkpoint_step must not exceed completed_steps",
            )
        )
    if not isinstance(policy.max_autonomous_steps, int) or policy.max_autonomous_steps < 1:
        issues.append(
            CampaignViolation(
                code="invalid-max-steps",
                message="max_autonomous_steps must be a positive integer",
            )
        )
    if not isinstance(policy.checkpoint_interval_steps, int) or policy.checkpoint_interval_steps < 1:
        issues.append(
            CampaignViolation(
                code="invalid-checkpoint-interval",
                message="checkpoint_interval_steps must be a positive integer",
            )
        )
    return tuple(issues)
