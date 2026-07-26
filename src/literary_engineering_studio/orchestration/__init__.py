"""Studio-owned adaptive planning above the formal Engine lifecycle."""

from .agent_transport import (
    OrchestrationAgentResponse,
    OrchestrationAgentTransport,
    RuntimeOrchestrationAgentTransport,
)
from .candidate import MACHINE_OWNED_FIELDS, parse_plan_candidate
from .compiler import PlanCompilationError, compile_plan, compiled_graph_digest
from .compiler_registry import CompilerRegistry
from .constitution import OrchestrationConstitution, constitution_v1
from .contracts import (
    CANDIDATE_SCHEMA,
    COMPILED_GRAPH_SCHEMA,
    PLAN_PATCH_SCHEMA,
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
    SceneFallbackLevel,
    TaskBinding,
    to_primitive,
)
from .patch import (
    PlanPatchDiff,
    ScenePlanPatchEvaluation,
    creative_plan_digest,
    evaluate_scene_plan_patch,
    parse_scene_plan_patch,
)
from .scene_binding import (
    SceneExecutionPolicy,
    SceneTaskPlanBinding,
    bind_scene_task,
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
from .service import ShadowOrchestrationService
from .shadow_run import (
    FixedRouteComparison,
    ShadowOrchestrationResult,
    ShadowPlanningInput,
)
from .profiles import (
    OrchestrationAgentProfile,
    OrchestrationAgentRole,
    orchestration_profile,
)
from .plan_events import (
    CREATIVE_PLAN_EVENT_SCHEMA,
    CreativePlanEvent,
    CreativePlanEventType,
    completed_candidate_from_event,
    parse_creative_plan_event,
)
from .shadow import (
    ShadowPlanEvaluation,
    ShadowStageTiming,
    evaluate_completed_shadow_candidate,
    evaluate_shadow_candidate,
)
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
    "PLAN_PATCH_SCHEMA",
    "PLAN_SCHEMA",
    "CompiledTaskGraph",
    "CompiledTaskNode",
    "CompilerRegistry",
    "CreativeExecutionPlan",
    "CreativeExecutionPlanCandidate",
    "CreativePlanEvent",
    "CreativePlanEventType",
    "CREATIVE_PLAN_EVENT_SCHEMA",
    "DefaultPlanFactory",
    "FixedRouteComparison",
    "FreedomBudget",
    "NormalizationContext",
    "OrchestrationMode",
    "OrchestrationAgentProfile",
    "OrchestrationAgentResponse",
    "OrchestrationAgentRole",
    "OrchestrationAgentTransport",
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
    "SceneExecutionPolicy",
    "SceneFallbackLevel",
    "ScenePlanPatchEvaluation",
    "SceneTaskPlanBinding",
    "PlanPatchDiff",
    "RuntimeOrchestrationAgentTransport",
    "FormalTaskObservation",
    "FormalTaskStatus",
    "SimulatedNode",
    "SimulatedResourceConflict",
    "ShadowPlanEvaluation",
    "ShadowOrchestrationResult",
    "ShadowOrchestrationService",
    "ShadowPlanningInput",
    "ShadowStageTiming",
    "StrategyPreset",
    "TaskBinding",
    "TruthPartition",
    "compile_plan",
    "compiled_graph_digest",
    "creative_plan_digest",
    "candidate_digest",
    "constitution_v1",
    "evaluate_shadow_candidate",
    "evaluate_completed_shadow_candidate",
    "evaluate_scene_plan_patch",
    "activate_persisted_revision",
    "lint_plan",
    "normalize_plan_candidate",
    "orchestration_settings",
    "orchestration_profile",
    "parse_plan_candidate",
    "parse_scene_plan_patch",
    "bind_scene_task",
    "parse_creative_plan_event",
    "completed_candidate_from_event",
    "partition_can_satisfy_formal_gate",
    "persist_shadow_revision",
    "simulate_plan",
    "to_primitive",
    "verify_persisted_revision",
]
