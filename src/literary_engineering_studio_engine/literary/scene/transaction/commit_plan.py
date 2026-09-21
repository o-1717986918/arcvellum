"""Pure construction of an atomic scene commit intent."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    CreativeResult,
    ReviewDecision,
    ReviewResult,
    SceneDelta,
    VerificationReport,
)
from .policy import ScenePolicy


@dataclass(frozen=True)
class SceneCommitPlan:
    transaction_id: str
    scene_id: str
    base_revision: str
    prose: str
    scene_delta: SceneDelta
    review_decision: ReviewDecision | None
    steward_approved: bool
    review_deferred_by_policy: bool = False


def commit_plan_issues(
    *,
    transaction_id: str,
    base_revision: str,
    verification: VerificationReport,
    policy: ScenePolicy,
    review: ReviewResult | None,
    steward_approved: bool,
) -> tuple[str, ...]:
    issues: list[str] = []
    if not transaction_id.strip():
        issues.append("transaction_id is required")
    if not base_revision.strip():
        issues.append("base_revision is required")
    if not verification.can_commit:
        issues.append("deterministic verification contains hard failures")
    if policy.independent_review_required and review is None:
        issues.append("independent review is required")
    if review is not None and review.decision is not ReviewDecision.PASS:
        issues.append(f"review decision is {review.decision.value}")
    if policy.steward_approval_required and not steward_approved:
        issues.append("steward approval is required")
    return tuple(issues)


def build_scene_commit_plan(
    *,
    transaction_id: str,
    base_revision: str,
    result: CreativeResult,
    verification: VerificationReport,
    policy: ScenePolicy,
    review: ReviewResult | None = None,
    steward_approved: bool = False,
) -> SceneCommitPlan:
    """Return a commit intent only after all policy prerequisites pass."""

    issues = commit_plan_issues(
        transaction_id=transaction_id,
        base_revision=base_revision,
        verification=verification,
        policy=policy,
        review=review,
        steward_approved=steward_approved,
    )
    if issues:
        raise ValueError("scene is not committable: " + "; ".join(issues))
    return SceneCommitPlan(
        transaction_id=transaction_id,
        scene_id=verification.scene_id,
        base_revision=base_revision,
        prose=result.prose,
        scene_delta=result.scene_delta,
        review_decision=review.decision if review is not None else None,
        steward_approved=steward_approved,
        review_deferred_by_policy=(
            review is None
            and policy.defer_semantic_review_to_chapter
            and not policy.independent_review_required
        ),
    )


__all__ = ["SceneCommitPlan", "build_scene_commit_plan", "commit_plan_issues"]
