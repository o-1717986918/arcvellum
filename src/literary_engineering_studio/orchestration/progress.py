"""Plan-level Progress Contract and no-progress fingerprint (AO-7, W6-8A).

The fingerprint is computed from formal project facts only; Agent-reported
progress is never accepted.  Two identical fingerprints for the same scope
mean no formal progress was made.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from ..protocols.violations import ContractViolation


@dataclass(frozen=True)
class ProgressFingerprintInput:
    scope_key: str
    formal_artifact_digests: tuple[tuple[str, str], ...] = ()
    completed_task_ids: tuple[str, ...] = ()
    passed_gate_ids: tuple[str, ...] = ()
    promoted_hanzi: int = 0
    obligation_updates: tuple[tuple[str, str], ...] = ()
    review_revision_binding: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ProgressFingerprint:
    scope_key: str
    fingerprint: str


ProgressFingerprintViolation = ContractViolation


def progress_fingerprint(
    inputs: ProgressFingerprintInput,
) -> ProgressFingerprint:
    """Return the deterministic formal progress identity for a scope."""
    payload = {
        "scope_key": inputs.scope_key,
        "formal_artifact_digests": sorted(inputs.formal_artifact_digests),
        "completed_task_ids": sorted(inputs.completed_task_ids),
        "passed_gate_ids": sorted(inputs.passed_gate_ids),
        "promoted_hanzi": inputs.promoted_hanzi,
        "obligation_updates": sorted(inputs.obligation_updates),
        "review_revision_binding": sorted(inputs.review_revision_binding),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ProgressFingerprint(
        scope_key=inputs.scope_key,
        fingerprint=digest,
    )


def no_progress_detected(
    previous: ProgressFingerprint,
    current: ProgressFingerprint,
) -> bool:
    """Two identical fingerprints for the same scope mean no progress."""
    if previous.scope_key != current.scope_key:
        return False
    return previous.fingerprint == current.fingerprint


def progress_input_violations(
    inputs: ProgressFingerprintInput,
) -> tuple[ProgressFingerprintViolation, ...]:
    """Return deterministic structural violations for progress inputs."""
    issues: list[ProgressFingerprintViolation] = []
    if not inputs.scope_key:
        issues.append(
            ProgressFingerprintViolation(
                code="missing-scope-key",
                message="scope_key must not be empty",
            )
        )
    if not isinstance(inputs.promoted_hanzi, int) or inputs.promoted_hanzi < 0:
        issues.append(
            ProgressFingerprintViolation(
                code="invalid-promoted-hanzi",
                message="promoted_hanzi must be a non-negative integer",
            )
        )
    artifact_paths = [path for path, _ in inputs.formal_artifact_digests]
    if len(artifact_paths) != len(set(artifact_paths)):
        issues.append(
            ProgressFingerprintViolation(
                code="duplicate-artifact-path",
                message="formal_artifact_digests must not contain duplicate paths",
            )
        )
    for path, digest in inputs.formal_artifact_digests:
        if not path or not digest:
            issues.append(
                ProgressFingerprintViolation(
                    code="invalid-artifact-digest",
                    message="artifact digest pairs must be non-empty",
                )
            )
    return tuple(issues)
