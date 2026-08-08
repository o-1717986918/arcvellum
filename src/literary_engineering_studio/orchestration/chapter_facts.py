"""Deterministic chapter planning facts for AO-5 (W6-6B).

These facts are the machine-owned projection boundary for chapter-level
planning.  They carry scene inventory, word targets, rhythm and promise
obligation identities, and deterministic risk signals.  The module never
reads the filesystem, never creates tasks, and never writes project facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocols.violations import ContractViolation

_RISK_FEATURE_NAMES = (
    "canon_change",
    "character_state_change",
    "new_asset_risk",
    "branch_ambiguity",
    "climax_weight",
    "continuity_debt",
    "style_novelty",
)


class ChapterFactsValidationMode(str, Enum):
    STRUCTURAL = "structural"
    PRODUCTION = "production"


@dataclass(frozen=True)
class ScenePlanningFact:
    scene_ref: str
    word_target: int = 0
    function: str = ""
    pace: str = ""
    canon_change: int = 0
    character_state_change: int = 0
    new_asset_risk: int = 0
    branch_ambiguity: int = 0
    climax_weight: int = 0
    continuity_debt: int = 0
    style_novelty: int = 0
    obligations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChapterPlanningFacts:
    chapter_id: str
    scenes: tuple[ScenePlanningFact, ...]
    chapter_word_target: int = 0
    rhythm_contract_hash: str = ""
    promise_obligation_ids: tuple[str, ...] = ()
    obligation_contract_present: bool = False
    base_project_revision: str = ""


ChapterFactViolation = ContractViolation


def scene_order(facts: ChapterPlanningFacts) -> tuple[str, ...]:
    """Return the ordered scene references from chapter planning facts."""
    return tuple(scene.scene_ref for scene in facts.scenes)


def chapter_facts_violations(
    facts: ChapterPlanningFacts,
    *,
    mode: ChapterFactsValidationMode = ChapterFactsValidationMode.STRUCTURAL,
) -> tuple[ChapterFactViolation, ...]:
    """Return deterministic structural violations for planning facts."""
    issues: list[ChapterFactViolation] = []
    if not facts.chapter_id:
        issues.append(
            ChapterFactViolation(
                code="missing-chapter-id",
                message="chapter_id must not be empty",
            )
        )
    if not facts.scenes:
        issues.append(
            ChapterFactViolation(
                code="empty-scene-inventory",
                message="scenes must not be empty",
            )
        )
        return tuple(issues)
    refs = scene_order(facts)
    if len(set(refs)) != len(refs):
        issues.append(
            ChapterFactViolation(
                code="duplicate-scene-refs",
                message="scene_refs must not contain duplicates",
            )
        )
    for scene in facts.scenes:
        if not scene.scene_ref:
            issues.append(
                ChapterFactViolation(
                    code="missing-scene-ref",
                    message="scene_ref must not be empty",
                )
            )
        if not isinstance(scene.word_target, int) or scene.word_target < 0:
            issues.append(
                ChapterFactViolation(
                    code="invalid-word-target",
                    message=f"word_target must be a non-negative integer: {scene.scene_ref}",
                )
            )
        for name in _RISK_FEATURE_NAMES:
            value = getattr(scene, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                issues.append(
                    ChapterFactViolation(
                        code="invalid-risk-feature",
                        message=f"{name} must be a non-negative integer: {scene.scene_ref}",
                    )
                )
    if facts.chapter_word_target < 0:
        issues.append(
            ChapterFactViolation(
                code="invalid-chapter-word-target",
                message="chapter_word_target must be non-negative",
            )
        )
    if mode is ChapterFactsValidationMode.PRODUCTION:
        issues.extend(_production_violations(facts))
    return tuple(issues)


def _production_violations(
    facts: ChapterPlanningFacts,
) -> list[ChapterFactViolation]:
    issues: list[ChapterFactViolation] = []
    if not facts.base_project_revision:
        issues.append(
            ChapterFactViolation(
                code="missing-base-project-revision",
                message="base_project_revision is required in production mode",
            )
        )
    if facts.chapter_word_target <= 0:
        issues.append(
            ChapterFactViolation(
                code="missing-chapter-word-target",
                message="chapter_word_target must be positive in production mode",
            )
        )
    if not facts.rhythm_contract_hash:
        issues.append(
            ChapterFactViolation(
                code="missing-rhythm-contract",
                message="rhythm_contract_hash is required in production mode",
            )
        )
    if not facts.obligation_contract_present:
        issues.append(
            ChapterFactViolation(
                code="missing-obligation-contract",
                message="an explicit chapter obligation contract is required",
            )
        )
    for scene in facts.scenes:
        if scene.word_target <= 0:
            issues.append(
                ChapterFactViolation(
                    code="missing-scene-word-target",
                    message=f"scene word target is required: {scene.scene_ref}",
                )
            )
        if not scene.function:
            issues.append(
                ChapterFactViolation(
                    code="missing-scene-function",
                    message=f"scene function is required: {scene.scene_ref}",
                )
            )
        if not scene.pace:
            issues.append(
                ChapterFactViolation(
                    code="missing-scene-pace",
                    message=f"scene pace is required: {scene.scene_ref}",
                )
            )
    return issues


def scene_risk_values(
    scene: ScenePlanningFact,
) -> tuple[tuple[str, int], ...]:
    """Return the deterministic risk signal pairs for a scene."""
    return tuple((name, getattr(scene, name)) for name in _RISK_FEATURE_NAMES)
