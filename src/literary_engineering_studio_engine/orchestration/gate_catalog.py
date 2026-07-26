"""Stable mandatory Gate identifiers for compiled creative plans."""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping


class GateId(StrEnum):
    CONTEXT = "context"
    CANON_CONTEXT = "canon-context"
    CHARACTER_STATE = "character-state"
    WORD_BUDGET = "word-budget"
    SCENE_FUNCTION = "scene-function"
    RHYTHM_CONTRACT = "rhythm-contract"
    BRIDGE_CONTRACT = "bridge-contract"
    MOUNTED_STYLE = "mounted-style"
    CAUSAL_SIMULATION = "causal-simulation"
    FULL_ROLEPLAY = "full-roleplay"
    BRANCH_DECISION = "branch-decision"
    COMPOSITION = "composition"
    PROSE_SINGLE_WRITER = "prose-single-writer"
    DETERMINISTIC_STYLE_LINT = "deterministic-style-lint"
    INDEPENDENT_SEMANTIC_REVIEW = "independent-semantic-review"
    EXACT_CANDIDATE_REVIEW = "exact-candidate-review"
    FRESH_REVISION_REVIEW = "fresh-revision-review"
    PROMOTION = "promotion"
    STATE_PATCH = "state-patch"
    STATE_SEMANTIC_REVIEW = "state-semantic-review"
    CANON_PATCH = "canon-patch"
    CONTINUITY_PATCH = "continuity-patch"
    CHAPTER_AUDIT = "chapter-audit"
    LONGFORM_AUDIT = "longform-audit"
    HUMAN_APPROVAL = "human-approval"
    RELEASE_READINESS = "release-readiness"


_NODE_GATES: dict[str, tuple[GateId, ...]] = {
    "creative_analysis": (GateId.CONTEXT,),
    "context_preparation": (
        GateId.CANON_CONTEXT,
        GateId.CHARACTER_STATE,
    ),
    "asset_candidate": (
        GateId.INDEPENDENT_SEMANTIC_REVIEW,
        GateId.HUMAN_APPROVAL,
    ),
    "roleplay_simulation": (
        GateId.CONTEXT,
        GateId.CAUSAL_SIMULATION,
    ),
    "scene_branch_simulation": (
        GateId.CAUSAL_SIMULATION,
        GateId.BRANCH_DECISION,
    ),
    "branch_selection": (GateId.BRANCH_DECISION,),
    "scene_composition": (
        GateId.WORD_BUDGET,
        GateId.SCENE_FUNCTION,
        GateId.RHYTHM_CONTRACT,
        GateId.BRIDGE_CONTRACT,
        GateId.MOUNTED_STYLE,
        GateId.BRANCH_DECISION,
    ),
    "formal_scene_prose": (
        GateId.CANON_CONTEXT,
        GateId.CHARACTER_STATE,
        GateId.WORD_BUDGET,
        GateId.SCENE_FUNCTION,
        GateId.RHYTHM_CONTRACT,
        GateId.BRIDGE_CONTRACT,
        GateId.MOUNTED_STYLE,
        GateId.CAUSAL_SIMULATION,
        GateId.BRANCH_DECISION,
        GateId.COMPOSITION,
        GateId.PROSE_SINGLE_WRITER,
    ),
    "formal_scene_review": (
        GateId.DETERMINISTIC_STYLE_LINT,
        GateId.INDEPENDENT_SEMANTIC_REVIEW,
        GateId.EXACT_CANDIDATE_REVIEW,
    ),
    "scene_revision": (
        GateId.PROSE_SINGLE_WRITER,
        GateId.FRESH_REVISION_REVIEW,
    ),
    "state_evolution": (
        GateId.STATE_PATCH,
        GateId.STATE_SEMANTIC_REVIEW,
    ),
    "canon_evolution": (
        GateId.CANON_PATCH,
        GateId.INDEPENDENT_SEMANTIC_REVIEW,
        GateId.HUMAN_APPROVAL,
    ),
    "chapter_audit": (GateId.CHAPTER_AUDIT,),
    "longform_audit": (GateId.LONGFORM_AUDIT,),
    "formal_export": (
        GateId.LONGFORM_AUDIT,
        GateId.RELEASE_READINESS,
        GateId.HUMAN_APPROVAL,
    ),
}

_FULL_ROLEPLAY_FEATURES = frozenset(
    {
        "new_character",
        "new_location",
        "new_world_rule",
        "major_relationship_change",
        "death",
        "betrayal",
        "time_jump",
    }
)


def mandatory_gates_for(
    *,
    node_kind: str,
    risk_features: Mapping[str, bool] | None = None,
) -> tuple[str, ...]:
    """Return machine-owned Gate IDs; plan text cannot remove them."""

    try:
        gates = list(_NODE_GATES[node_kind])
    except KeyError as exc:
        raise ValueError(f"unsupported plan node kind: {node_kind}") from exc
    features = risk_features or {}
    if node_kind in {"roleplay_simulation", "scene_branch_simulation", "formal_scene_prose"} and any(
        bool(features.get(name)) for name in _FULL_ROLEPLAY_FEATURES
    ):
        gates.append(GateId.FULL_ROLEPLAY)
    return tuple(dict.fromkeys(gate.value for gate in gates))
