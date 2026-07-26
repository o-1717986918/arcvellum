"""Immutable contracts for adaptive creative plans and their intent."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any

from literary_engineering_studio_engine.orchestration import PlanNodeKind


CANDIDATE_SCHEMA = "arcvellum/creative-execution-plan-candidate/v1"
PLAN_SCHEMA = "arcvellum/creative-execution-plan/v1"


class PlanScopeKind(str, Enum):
    BOOK = "book"
    VOLUME = "volume"
    CHAPTER = "chapter"
    SCENE = "scene"


class RoleplayDepth(str, Enum):
    LIGHT = "light"
    TARGETED = "targeted"
    FULL = "full"


class RevisionPolicy(str, Enum):
    TARGETED_THEN_REWRITE = "targeted_then_rewrite"
    REWRITE = "rewrite"
    RETURN_TO_BRANCH = "return_to_branch"


class PlanLifecycleStatus(str, Enum):
    NORMALIZED = "normalized"
    REVIEWED = "reviewed"
    ACTIVE = "active"
    PAUSED = "paused"
    STALE = "stale"
    COMPLETE = "complete"
    REJECTED = "rejected"


class ReplanTrigger(str, Enum):
    REVIEW_FAILED = "review_failed"
    PROSE_FAILED_TWICE = "prose_failed_twice"
    NEW_CHARACTER_DETECTED = "new_character_detected"
    CANON_CONFLICT = "canon_conflict"
    BRANCH_AMBIGUOUS = "branch_scores_are_close"
    WORD_BUDGET_DRIFT = "word_budget_drift"
    SCENE_INVENTORY_INSUFFICIENT = "scene_inventory_insufficient"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    FORMAL_STATE_CHANGED = "formal_state_changed"
    USER_DIRECTION_CHANGED = "user_direction_changed"


@dataclass(frozen=True)
class PlanScope:
    kind: PlanScopeKind
    key: str
    volume_id: str = ""
    chapter_ids: tuple[str, ...] = ()
    scene_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanAssumption:
    statement: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeInterpretation:
    dramatic_problem: str
    reader_effect: str
    chapter_function: str
    assumptions: tuple[PlanAssumption, ...] = ()
    uncertainties: tuple[str, ...] = ()


@dataclass(frozen=True)
class SceneStrategy:
    scene_ref: str
    function: str
    pace: str
    roleplay_depth: RoleplayDepth


@dataclass(frozen=True)
class PromisePolicy:
    resolve: tuple[str, ...] = ()
    defer: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreativeStrategy:
    scene_inventory: tuple[SceneStrategy, ...] = ()
    branch_count: int = 3
    revision_policy: RevisionPolicy = RevisionPolicy.TARGETED_THEN_REWRITE
    narrative_distance: str = "adaptive"
    promise_policy: PromisePolicy = PromisePolicy()


@dataclass(frozen=True)
class PlanContribution:
    kind: str
    description: str


@dataclass(frozen=True)
class PlanParameter:
    name: str
    value: str | int | float | bool


@dataclass(frozen=True)
class ProgressContract:
    formal_artifact_delta: tuple[str, ...] = ()
    obligations_fulfilled: tuple[str, ...] = ()
    obligations_deferred: tuple[str, ...] = ()
    target_hanzi: int = 0
    word_tolerance: float = 0.08
    maximum_open_review_notes: int = 0
    expected_state_patch: str = ""


@dataclass(frozen=True)
class PlanTaskNode:
    node_id: str
    kind: PlanNodeKind
    scope_refs: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    requested_capabilities: tuple[str, ...] = ()
    parameters: tuple[PlanParameter, ...] = ()
    contribution: PlanContribution = PlanContribution(kind="evidence", description="")
    progress_contract: ProgressContract = ProgressContract()


@dataclass(frozen=True)
class ReplanRule:
    trigger: ReplanTrigger
    action: str
    threshold: int = 1


@dataclass(frozen=True)
class FreedomBudget:
    max_added_tasks: int = 8
    max_replans_per_scope: int = 2
    max_parallel_read_tasks: int = 3
    max_branch_count: int = 5
    max_research_tasks: int = 2
    max_research_cost: float = 5.0
    max_analysis_to_production_ratio: float = 0.35
    max_plan_depth: int = 32
    max_plan_stall_cycles: int = 2


@dataclass(frozen=True)
class CreativeExecutionPlanCandidate:
    schema: str
    scope: PlanScope
    objective: str
    interpretation: NarrativeInterpretation
    strategy: CreativeStrategy
    task_nodes: tuple[PlanTaskNode, ...]
    replan_rules: tuple[ReplanRule, ...]
    freedom_request: FreedomBudget


@dataclass(frozen=True)
class PlanGateBinding:
    node_id: str
    gate_ids: tuple[str, ...]


@dataclass(frozen=True)
class CreativeExecutionPlan:
    schema: str
    plan_id: str
    revision: int
    base_project_fingerprint: str
    constitution_version: str
    created_at: str
    lifecycle_status: PlanLifecycleStatus
    scope: PlanScope
    objective: str
    interpretation: NarrativeInterpretation
    strategy: CreativeStrategy
    task_nodes: tuple[PlanTaskNode, ...]
    replan_rules: tuple[ReplanRule, ...]
    freedom_budget: FreedomBudget
    route_macro_id: str
    route_sequence: tuple[str, ...]
    mandatory_gate_nodes: tuple[PlanGateBinding, ...]
    compiled_graph_digest: str = ""
    approved_by: str = ""
    candidate_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateParseResult:
    candidate: CreativeExecutionPlanCandidate
    warnings: tuple[str, ...]


def to_primitive(value: Any) -> Any:
    """Project plan DTOs to stable JSON-compatible values."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in sorted(value.items())}
    return value
