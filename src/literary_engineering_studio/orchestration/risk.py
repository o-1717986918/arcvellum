"""Machine-minimum SceneRiskProfile contracts for AO-5 adaptive depth.

The machine derives a minimum risk level from formal project facts; a
Planner may propose a higher level but can never lower the machine minimum.
The profile only informs depth/branch/review policy and never replaces the
mandatory formal Agent review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocols.violations import ContractViolation


class SceneRiskLevel(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    DEEP = "deep"


RISK_FEATURE_NAMES = (
    "canon_change",
    "character_state_change",
    "new_asset_risk",
    "branch_ambiguity",
    "climax_weight",
    "continuity_debt",
    "style_novelty",
)

_DEEP_THRESHOLDS = {
    "canon_change": 2,
    "character_state_change": 3,
    "new_asset_risk": 2,
    "branch_ambiguity": 3,
    "climax_weight": 4,
    "continuity_debt": 3,
    "style_novelty": 3,
}

_STANDARD_THRESHOLDS = {
    "canon_change": 1,
    "character_state_change": 1,
    "new_asset_risk": 1,
    "branch_ambiguity": 2,
    "climax_weight": 2,
    "continuity_debt": 1,
    "style_novelty": 1,
}

_RISK_LEVEL_ORDER = (SceneRiskLevel.COMPACT, SceneRiskLevel.STANDARD, SceneRiskLevel.DEEP)


@dataclass(frozen=True)
class SceneRiskFacts:
    scene_id: str
    canon_change: int = 0
    character_state_change: int = 0
    new_asset_risk: int = 0
    branch_ambiguity: int = 0
    climax_weight: int = 0
    continuity_debt: int = 0
    style_novelty: int = 0


@dataclass(frozen=True)
class SceneRiskProfile:
    scene_id: str
    level: SceneRiskLevel
    minimum_level: SceneRiskLevel
    canon_change: int = 0
    character_state_change: int = 0
    new_asset_risk: int = 0
    branch_ambiguity: int = 0
    climax_weight: int = 0
    continuity_debt: int = 0
    style_novelty: int = 0
    reasons: tuple[str, ...] = ()


SceneRiskViolation = ContractViolation


def machine_minimum_risk_level(facts: SceneRiskFacts) -> SceneRiskLevel:
    """Return the deterministic machine minimum for formal risk facts."""

    if _exceeds_any(facts, _DEEP_THRESHOLDS):
        return SceneRiskLevel.DEEP
    if _exceeds_any(facts, _STANDARD_THRESHOLDS):
        return SceneRiskLevel.STANDARD
    return SceneRiskLevel.COMPACT


def effective_risk_level(
    minimum: SceneRiskLevel,
    proposed: SceneRiskLevel,
) -> SceneRiskLevel:
    """A Planner proposal may raise the level but never lower it."""

    if _risk_order(proposed) >= _risk_order(minimum):
        return proposed
    return minimum


def build_scene_risk_profile(
    facts: SceneRiskFacts,
    *,
    proposed_level: SceneRiskLevel | None = None,
) -> SceneRiskProfile:
    """Project facts into a profile with the machine minimum preserved."""

    minimum = machine_minimum_risk_level(facts)
    level = (
        effective_risk_level(minimum, proposed_level)
        if proposed_level is not None
        else minimum
    )
    reasons = list(_machine_reasons(facts, minimum))
    if proposed_level is not None and _risk_order(proposed_level) > _risk_order(minimum):
        reasons.append(f"proposed-{proposed_level.value}-above-minimum-{minimum.value}")
    return SceneRiskProfile(
        scene_id=facts.scene_id,
        level=level,
        minimum_level=minimum,
        canon_change=facts.canon_change,
        character_state_change=facts.character_state_change,
        new_asset_risk=facts.new_asset_risk,
        branch_ambiguity=facts.branch_ambiguity,
        climax_weight=facts.climax_weight,
        continuity_debt=facts.continuity_debt,
        style_novelty=facts.style_novelty,
        reasons=tuple(reasons),
    )


def scene_risk_violations(facts: SceneRiskFacts) -> tuple[SceneRiskViolation, ...]:
    """Return deterministic input violations for risk facts."""

    issues: list[SceneRiskViolation] = []
    if not facts.scene_id:
        issues.append(
            SceneRiskViolation(
                code="missing-scene-id",
                message="scene_id must not be empty",
            )
        )
    for name in RISK_FEATURE_NAMES:
        value = getattr(facts, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(
                SceneRiskViolation(
                    code="invalid-risk-feature",
                    message=f"{name} must be a non-negative integer",
                )
            )
    return tuple(issues)


def _exceeds_any(facts: SceneRiskFacts, thresholds: dict[str, int]) -> bool:
    return any(getattr(facts, name) >= threshold for name, threshold in thresholds.items())


def _machine_reasons(facts: SceneRiskFacts, minimum: SceneRiskLevel) -> tuple[str, ...]:
    reasons: list[str] = []
    for name, threshold in _DEEP_THRESHOLDS.items():
        if getattr(facts, name) >= threshold:
            reasons.append(f"{name}>=deep:{threshold}")
    for name, threshold in _STANDARD_THRESHOLDS.items():
        if getattr(facts, name) >= threshold:
            reasons.append(f"{name}>=standard:{threshold}")
    if minimum == SceneRiskLevel.COMPACT:
        reasons.append("no-risk-feature-threshold")
    return tuple(reasons)


def _risk_order(level: SceneRiskLevel) -> int:
    return _RISK_LEVEL_ORDER.index(level)
