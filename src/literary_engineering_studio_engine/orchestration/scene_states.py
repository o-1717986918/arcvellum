"""Map formal scene route states onto adaptive plan node kinds."""

from __future__ import annotations

from .task_catalog import PlanNodeKind


_STATE_NODE_KINDS = {
    "context-packet": PlanNodeKind.CONTEXT_PREPARATION,
    "context-trace": PlanNodeKind.CONTEXT_PREPARATION,
    "roleplay-simulation": PlanNodeKind.ROLEPLAY_SIMULATION,
    "roleplay-agent-task": PlanNodeKind.ROLEPLAY_SIMULATION,
    "branch-manifest": PlanNodeKind.BRANCH_SIMULATION,
    "branch-agent-task": PlanNodeKind.BRANCH_SIMULATION,
    "branch-selection": PlanNodeKind.BRANCH_SELECTION,
    "composition-json": PlanNodeKind.SCENE_COMPOSITION,
    "composition-agent-task": PlanNodeKind.SCENE_COMPOSITION,
    "scene-word-budget-contract": PlanNodeKind.SCENE_COMPOSITION,
    "reader-experience-contract": PlanNodeKind.SCENE_COMPOSITION,
    "scene-rhythm-contract": PlanNodeKind.SCENE_COMPOSITION,
    "candidate-generation-provenance": PlanNodeKind.FORMAL_PROSE,
    "generation-agent-task": PlanNodeKind.FORMAL_PROSE,
    "candidate-review": PlanNodeKind.SEMANTIC_REVIEW,
    "agent-review-task": PlanNodeKind.SEMANTIC_REVIEW,
    "static-review": PlanNodeKind.SEMANTIC_REVIEW,
    "candidate-revision": PlanNodeKind.REVISION,
    "candidate-human-decision": PlanNodeKind.REVISION,
    "static-revision": PlanNodeKind.REVISION,
    "target-length-revision": PlanNodeKind.REVISION,
    "state-patch-json": PlanNodeKind.STATE_EVOLUTION,
    "state-agent-task": PlanNodeKind.STATE_EVOLUTION,
    "state-patch-approval": PlanNodeKind.STATE_EVOLUTION,
    "state-apply": PlanNodeKind.STATE_EVOLUTION,
    "canon-patch-json": PlanNodeKind.CANON_EVOLUTION,
    "canon-agent-task": PlanNodeKind.CANON_EVOLUTION,
}


def scene_plan_node_kind(current_state: str) -> PlanNodeKind | None:
    """Return the plan phase for an existing formal task, or passthrough."""

    return _STATE_NODE_KINDS.get(str(current_state or "").strip())
