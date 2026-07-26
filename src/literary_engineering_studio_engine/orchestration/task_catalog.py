"""Formal task capabilities exposed to the Studio plan compiler."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .gate_catalog import mandatory_gates_for


class PlanNodeKind(StrEnum):
    CREATIVE_ANALYSIS = "creative_analysis"
    CONTEXT_PREPARATION = "context_preparation"
    ASSET_CANDIDATE = "asset_candidate"
    ROLEPLAY_SIMULATION = "roleplay_simulation"
    BRANCH_SIMULATION = "scene_branch_simulation"
    BRANCH_SELECTION = "branch_selection"
    SCENE_COMPOSITION = "scene_composition"
    FORMAL_PROSE = "formal_scene_prose"
    SEMANTIC_REVIEW = "formal_scene_review"
    REVISION = "scene_revision"
    STATE_EVOLUTION = "state_evolution"
    CANON_EVOLUTION = "canon_evolution"
    CHAPTER_AUDIT = "chapter_audit"
    LONGFORM_AUDIT = "longform_audit"
    EXPORT = "formal_export"


@dataclass(frozen=True)
class FormalTaskCapability:
    capability_id: str
    node_kind: PlanNodeKind
    route: str
    allowed_task_types: tuple[str, ...]
    supported_scopes: tuple[str, ...]
    parameter_schema: str
    mandatory_gate_ids: tuple[str, ...]
    resource_templates: tuple[str, ...]
    progress_kind: str
    agent_role: str


def _capability(
    node_kind: PlanNodeKind,
    route: str,
    task_types: tuple[str, ...],
    scopes: tuple[str, ...],
    resources: tuple[str, ...],
    progress_kind: str,
    agent_role: str,
    parameter_schema: str = "builtin:none/v1",
) -> FormalTaskCapability:
    return FormalTaskCapability(
        capability_id=f"formal-task.{node_kind.value}.v1",
        node_kind=node_kind,
        route=route,
        allowed_task_types=task_types,
        supported_scopes=scopes,
        parameter_schema=parameter_schema,
        mandatory_gate_ids=mandatory_gates_for(node_kind=node_kind.value),
        resource_templates=resources,
        progress_kind=progress_kind,
        agent_role=agent_role,
    )


_CAPABILITIES = (
    _capability(
        PlanNodeKind.CREATIVE_ANALYSIS,
        "scene-development",
        ("platform-agent-judgment",),
        ("scene", "chapter"),
        ("scope:read", "analysis:candidate-write"),
        "evidence",
        "creative-analysis-agent",
        "builtin:creative-analysis/v1",
    ),
    _capability(
        PlanNodeKind.CONTEXT_PREPARATION,
        "scene-development",
        ("deterministic-cli",),
        ("scene",),
        ("scope:read", "context:candidate-write"),
        "context",
        "deterministic-engine",
    ),
    _capability(
        PlanNodeKind.ASSET_CANDIDATE,
        "character-and-world-assets",
        ("platform-agent-asset-creation", "platform-agent-revision"),
        ("asset", "scene", "chapter"),
        ("scope:read", "archive-candidate:candidate-write"),
        "candidate-asset",
        "main-creative-agent",
        "builtin:asset-candidate/v1",
    ),
    _capability(
        PlanNodeKind.ROLEPLAY_SIMULATION,
        "scene-development",
        ("deterministic-cli", "platform-agent-judgment"),
        ("scene",),
        ("scene:read", "roleplay:candidate-write"),
        "causal-evidence",
        "main-review-agent",
        "builtin:roleplay-depth/v1",
    ),
    _capability(
        PlanNodeKind.BRANCH_SIMULATION,
        "scene-development",
        ("deterministic-cli", "platform-agent-judgment"),
        ("scene",),
        ("scene:read", "branch:candidate-write"),
        "branch-evidence",
        "main-review-agent",
        "builtin:branch-simulation/v1",
    ),
    _capability(
        PlanNodeKind.BRANCH_SELECTION,
        "scene-development",
        ("platform-agent-judgment", "human-approval-boundary"),
        ("scene",),
        ("branch:read", "branch-selection:candidate-write"),
        "decision",
        "human-decision",
    ),
    _capability(
        PlanNodeKind.SCENE_COMPOSITION,
        "scene-development",
        ("deterministic-cli", "platform-agent-judgment"),
        ("scene",),
        ("scene:read", "composition:candidate-write"),
        "composition",
        "main-review-agent",
    ),
    _capability(
        PlanNodeKind.FORMAL_PROSE,
        "scene-development",
        ("main-platform-agent-prose",),
        ("scene",),
        ("scene:read", "prose-candidate:candidate-write"),
        "formal-prose-candidate",
        "main-creative-agent",
        "builtin:formal-prose/v1",
    ),
    _capability(
        PlanNodeKind.SEMANTIC_REVIEW,
        "scene-development",
        ("platform-agent-review", "deterministic-review"),
        ("scene",),
        ("prose-candidate:read", "review:candidate-write"),
        "review-evidence",
        "main-review-agent",
    ),
    _capability(
        PlanNodeKind.REVISION,
        "scene-development",
        ("main-platform-agent-prose-revision",),
        ("scene",),
        ("prose-candidate:read", "prose-revision:candidate-write"),
        "formal-prose-candidate",
        "main-creative-agent",
        "builtin:revision-policy/v1",
    ),
    _capability(
        PlanNodeKind.STATE_EVOLUTION,
        "scene-development",
        ("platform-agent-review", "deterministic-cli"),
        ("scene",),
        ("promoted-prose:read", "state-patch:candidate-write"),
        "state-patch",
        "state-analyst",
    ),
    _capability(
        PlanNodeKind.CANON_EVOLUTION,
        "review-and-audit",
        ("platform-agent-review", "human-approval-boundary", "deterministic-cli"),
        ("scene", "chapter"),
        ("promoted-prose:read", "canon-patch:candidate-write"),
        "canon-patch",
        "main-review-agent",
    ),
    _capability(
        PlanNodeKind.CHAPTER_AUDIT,
        "review-and-audit",
        ("platform-agent-review", "deterministic-cli"),
        ("chapter",),
        ("chapter:read", "chapter-audit:candidate-write"),
        "audit",
        "main-review-agent",
    ),
    _capability(
        PlanNodeKind.LONGFORM_AUDIT,
        "review-and-audit",
        ("platform-agent-review", "deterministic-cli"),
        ("book", "volume"),
        ("project:read", "longform-audit:candidate-write"),
        "audit",
        "main-review-agent",
    ),
    _capability(
        PlanNodeKind.EXPORT,
        "export-and-release",
        ("deterministic-cli", "human-approval-boundary"),
        ("book", "volume", "chapter"),
        ("formal-project:read", "release:formal-write"),
        "release",
        "deterministic-engine",
    ),
)
_BY_KIND = {item.node_kind: item for item in _CAPABILITIES}


def formal_task_capabilities() -> tuple[FormalTaskCapability, ...]:
    return _CAPABILITIES


def formal_task_capability(node_kind: PlanNodeKind | str) -> FormalTaskCapability:
    try:
        normalized = node_kind if isinstance(node_kind, PlanNodeKind) else PlanNodeKind(node_kind)
        return _BY_KIND[normalized]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unsupported plan node kind: {node_kind}") from exc
