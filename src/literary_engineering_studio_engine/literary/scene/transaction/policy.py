"""Risk-driven policy for one lean scene transaction."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SceneExecutionMode, SceneRisk, SceneRiskLevel


@dataclass(frozen=True)
class ScenePolicy:
    mode: SceneExecutionMode
    risk: SceneRisk
    independent_review_required: bool
    explicit_decision_trace_required: bool
    defer_semantic_review_to_chapter: bool
    automatic_revision_allowed: bool
    max_revision_attempts: int
    steward_approval_required: bool


def derive_scene_policy(
    *,
    mode: SceneExecutionMode,
    risk: SceneRisk,
) -> ScenePolicy:
    """Resolve the review matrix; callers cannot lower the supplied risk."""

    if mode is SceneExecutionMode.STRICT_V1:
        return ScenePolicy(
            mode=mode,
            risk=risk,
            independent_review_required=True,
            explicit_decision_trace_required=True,
            defer_semantic_review_to_chapter=False,
            automatic_revision_allowed=True,
            max_revision_attempts=1,
            steward_approval_required=risk.level is SceneRiskLevel.HIGH,
        )

    high = risk.level is SceneRiskLevel.HIGH
    standard = risk.level is SceneRiskLevel.STANDARD
    draft = mode is SceneExecutionMode.DRAFT
    publication = mode is SceneExecutionMode.PUBLICATION
    return ScenePolicy(
        mode=mode,
        risk=risk,
        independent_review_required=high or ((standard or publication) and not draft),
        explicit_decision_trace_required=high,
        defer_semantic_review_to_chapter=(draft or (risk.level is SceneRiskLevel.LOW and not publication)),
        automatic_revision_allowed=True,
        max_revision_attempts=1,
        steward_approval_required=high,
    )


__all__ = ["ScenePolicy", "derive_scene_policy"]
