"""Studio-owned adaptive planning above the formal Engine lifecycle."""

from .candidate import MACHINE_OWNED_FIELDS, parse_plan_candidate
from .compiler import PlanCompilationError, compile_plan, compiled_graph_digest
from .compiler_registry import CompilerRegistry
from .constitution import OrchestrationConstitution, constitution_v1
from .contracts import (
    CANDIDATE_SCHEMA,
    COMPILED_GRAPH_SCHEMA,
    PLAN_SCHEMA,
    CompiledTaskGraph,
    CompiledTaskNode,
    CreativeExecutionPlan,
    CreativeExecutionPlanCandidate,
    FreedomBudget,
    PlanLifecycleStatus,
    PlanScopeKind,
    ReplanTrigger,
    RevisionPolicy,
    RoleplayDepth,
    TaskBinding,
    to_primitive,
)
from .defaults import DefaultPlanFactory
from .lint import PlanIssue, PlanIssueSeverity, PlanLintContext, PlanLintResult, lint_plan
from .normalizer import NormalizationContext, candidate_digest, normalize_plan_candidate
from .persistence import (
    OrchestrationAuditArtifacts,
    activate_persisted_revision,
    persist_shadow_revision,
    verify_persisted_revision,
)
from .simulator import (
    FormalTaskObservation,
    FormalTaskStatus,
    PlanSimulationContext,
    PlanSimulationResult,
    SimulatedNode,
    SimulatedResourceConflict,
    simulate_plan,
)
from .settings import (
    OrchestrationMode,
    OrchestrationSettings,
    StrategyPreset,
    orchestration_settings,
)
from .profiles import (
    OrchestrationAgentProfile,
    OrchestrationAgentRole,
    orchestration_profile,
)
from .shadow import ShadowPlanEvaluation, ShadowStageTiming, evaluate_shadow_candidate
from .truth_partition import (
    AssertionKind,
    ProvenanceRef,
    TruthPartition,
    partition_can_satisfy_formal_gate,
)

__all__ = [
    "AssertionKind",
    "CANDIDATE_SCHEMA",
    "COMPILED_GRAPH_SCHEMA",
    "MACHINE_OWNED_FIELDS",
    "PLAN_SCHEMA",
    "CompiledTaskGraph",
    "CompiledTaskNode",
    "CompilerRegistry",
    "CreativeExecutionPlan",
    "CreativeExecutionPlanCandidate",
    "DefaultPlanFactory",
    "FreedomBudget",
    "NormalizationContext",
    "OrchestrationMode",
    "OrchestrationAgentProfile",
    "OrchestrationAgentRole",
    "OrchestrationConstitution",
    "OrchestrationAuditArtifacts",
    "OrchestrationSettings",
    "PlanIssue",
    "PlanIssueSeverity",
    "PlanCompilationError",
    "PlanLifecycleStatus",
    "PlanLintContext",
    "PlanLintResult",
    "PlanSimulationContext",
    "PlanSimulationResult",
    "PlanScopeKind",
    "ProvenanceRef",
    "ReplanTrigger",
    "RevisionPolicy",
    "RoleplayDepth",
    "FormalTaskObservation",
    "FormalTaskStatus",
    "SimulatedNode",
    "SimulatedResourceConflict",
    "ShadowPlanEvaluation",
    "ShadowStageTiming",
    "StrategyPreset",
    "TaskBinding",
    "TruthPartition",
    "compile_plan",
    "compiled_graph_digest",
    "candidate_digest",
    "constitution_v1",
    "evaluate_shadow_candidate",
    "activate_persisted_revision",
    "lint_plan",
    "normalize_plan_candidate",
    "orchestration_settings",
    "orchestration_profile",
    "parse_plan_candidate",
    "partition_can_satisfy_formal_gate",
    "persist_shadow_revision",
    "simulate_plan",
    "to_primitive",
    "verify_persisted_revision",
]
