"""ResourceGate admission for AO-6 bounded concurrency (W6-7C).

The gate admits only read-only, pairwise non-conflicting claims into
parallel groups; every claim with writes is serialized as a singleton.
Conflicts reuse the existing ``claims_conflict`` contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from literary_engineering_studio.runtime.resources import (
    ResourceClaim,
    claims_conflict,
)


@dataclass(frozen=True)
class ParallelGroup:
    task_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResourceGateViolation:
    code: str
    message: str


@dataclass(frozen=True)
class AdmissionPlan:
    parallel_groups: tuple[ParallelGroup, ...]
    serialized: tuple[str, ...]
    violations: tuple[ResourceGateViolation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


def admission_plan(
    claims: Sequence[ResourceClaim],
    *,
    max_parallel_read_tasks: int = 3,
) -> AdmissionPlan:
    """Partition claims into parallel read-only groups and serial writers."""
    violations = _input_violations(claims, max_parallel_read_tasks)
    if violations:
        return AdmissionPlan(
            parallel_groups=(),
            serialized=(),
            violations=violations,
        )
    read_only = [
        claim for claim in claims if not claim.writes and not claim.exclusive_barriers
    ]
    writers = [
        claim for claim in claims if claim.writes or claim.exclusive_barriers
    ]
    groups = _read_only_groups(read_only, max_parallel_read_tasks)
    return AdmissionPlan(
        parallel_groups=groups,
        serialized=tuple(claim.task_node_id for claim in writers),
        violations=violations,
    )


def _read_only_groups(
    claims: list[ResourceClaim],
    max_parallel_read_tasks: int,
) -> tuple[ParallelGroup, ...]:
    groups: list[list[ResourceClaim]] = []
    for claim in sorted(claims, key=lambda item: item.task_node_id):
        placed = False
        for group in groups:
            if len(group) >= max_parallel_read_tasks:
                continue
            if all(not claims_conflict(claim, member).conflicts for member in group):
                group.append(claim)
                placed = True
                break
        if not placed:
            groups.append([claim])
    return tuple(
        ParallelGroup(task_node_ids=tuple(item.task_node_id for item in group))
        for group in groups
    )


def _input_violations(
    claims: Sequence[ResourceClaim],
    max_parallel_read_tasks: int,
) -> tuple[ResourceGateViolation, ...]:
    issues: list[ResourceGateViolation] = []
    if max_parallel_read_tasks < 1:
        issues.append(
            ResourceGateViolation(
                code="invalid-parallel-limit",
                message="max_parallel_read_tasks must be at least 1",
            )
        )
    node_ids = [claim.task_node_id for claim in claims]
    if len(node_ids) != len(set(node_ids)):
        issues.append(
            ResourceGateViolation(
                code="duplicate-claim",
                message="task_node_id must be unique across claims",
            )
        )
    for claim in claims:
        if not claim.task_node_id:
            issues.append(
                ResourceGateViolation(
                    code="missing-claim-id",
                    message="task_node_id must not be empty",
                )
            )
    return tuple(dict.fromkeys(issues))
