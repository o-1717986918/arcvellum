"""Bounded local output repair contracts (AO-6, W6-7C).

Repair is limited to missing or structurally invalid expected outputs.
Passed outputs are preserved read-only, semantic failure is never disguised
as format repair, and every repair re-runs the full deterministic preflight.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputRepairRequest:
    task_id: str
    bundle_id: str
    invalid_outputs: tuple[str, ...]
    preserved_outputs: tuple[str, ...]
    preflight_issue_ids: tuple[str, ...]
    attempt: int


@dataclass(frozen=True)
class RepairViolation:
    code: str
    message: str


@dataclass(frozen=True)
class RepairDecision:
    allowed: bool
    reasons: tuple[str, ...]


def repair_request_violations(
    request: OutputRepairRequest,
    *,
    max_attempts: int,
) -> tuple[RepairViolation, ...]:
    """Return deterministic structural violations for a repair request."""
    issues: list[RepairViolation] = []
    if not request.task_id:
        issues.append(
            RepairViolation(
                code="missing-task-id",
                message="task_id must not be empty",
            )
        )
    if not request.bundle_id:
        issues.append(
            RepairViolation(
                code="missing-bundle-id",
                message="bundle_id must not be empty",
            )
        )
    if not request.invalid_outputs:
        issues.append(
            RepairViolation(
                code="empty-invalid-outputs",
                message="invalid_outputs must not be empty",
            )
        )
    if not request.preflight_issue_ids:
        issues.append(
            RepairViolation(
                code="empty-preflight-issues",
                message="preflight_issue_ids must not be empty",
            )
        )
    if not 1 <= request.attempt <= max_attempts:
        issues.append(
            RepairViolation(
                code="attempt-out-of-budget",
                message=f"attempt must be between 1 and {max_attempts}",
            )
        )
    overlap = set(request.invalid_outputs).intersection(
        request.preserved_outputs
    )
    if overlap:
        issues.append(
            RepairViolation(
                code="preserved-output-targeted",
                message=f"preserved outputs must not be repaired: {sorted(overlap)[0]}",
            )
        )
    return tuple(issues)


def repair_allowed(
    request: OutputRepairRequest,
    *,
    max_attempts: int,
) -> RepairDecision:
    """A repair is allowed only when the request is structurally valid."""
    violations = repair_request_violations(
        request,
        max_attempts=max_attempts,
    )
    return RepairDecision(
        allowed=not violations,
        reasons=tuple(item.code for item in violations),
    )
