"""Bind an active scene plan to tasks from the existing formal Engine route."""

from __future__ import annotations

from dataclasses import dataclass, replace

from literary_engineering_studio_engine.public.orchestration import (
    PlanNodeKind,
    scene_plan_node_kind,
)

from ..contracts import TaskPackage
from .chapter_binding import (
    ChapterWindowPolicy,
    chapter_scene_minimums,
    stronger_roleplay_depth,
)
from .compiler import compiled_graph_digest
from .contracts import (
    CompiledTaskGraph,
    CompiledTaskNode,
    CreativeExecutionPlan,
    SceneFallbackLevel,
)


@dataclass(frozen=True)
class SceneExecutionPolicy:
    scene_id: str
    roleplay_depth: str
    branch_count: int
    revision_policy: str
    fallback_level: str
    narrative_distance: str

    def as_dict(self) -> dict[str, object]:
        return {
            "scene_id": self.scene_id,
            "roleplay_depth": self.roleplay_depth,
            "branch_count": self.branch_count,
            "revision_policy": self.revision_policy,
            "fallback_level": self.fallback_level,
            "narrative_distance": self.narrative_distance,
        }


@dataclass(frozen=True)
class SceneTaskPlanBinding:
    task: TaskPackage
    status: str
    plan_id: str
    plan_revision: int
    node_id: str
    node_kind: str
    policy: SceneExecutionPolicy


def bind_scene_task(
    task: TaskPackage,
    *,
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    current_project_fingerprint: str,
    chapter_policy: ChapterWindowPolicy | None = None,
    chapter_policy_digest: str = "",
) -> SceneTaskPlanBinding:
    """Project strategy onto one formal task without replacing its lifecycle."""

    scene_id = str(task.payload.get("scene_id") or "").strip()
    if task.route != "scene-development" or not scene_id:
        raise ValueError("scene plan binding requires a formal scene-development task")
    _validate_chain(plan, graph, current_project_fingerprint)
    if scene_id not in _scene_refs(plan):
        raise ValueError("formal task scene is outside the active plan scope")
    policy = _scene_policy(
        plan,
        graph,
        scene_id,
        chapter_policy=chapter_policy,
    )
    node_kind = scene_plan_node_kind(task.current_state)
    if node_kind is None:
        return _binding_result(
            task,
            plan=plan,
            node=None,
            policy=policy,
            status="formal_lifecycle_passthrough",
            node_kind="",
            chapter_policy=chapter_policy,
            chapter_policy_digest=chapter_policy_digest,
        )
    node = _resolve_node(task, graph, scene_id, node_kind)
    if node is None:
        if node_kind is not PlanNodeKind.REVISION:
            raise RuntimeError(
                "active scene plan lacks the node required by the formal task: "
                f"{node_kind.value}"
            )
        return _binding_result(
            task,
            plan=plan,
            node=None,
            policy=policy,
            status="formal_conditional_policy",
            node_kind=node_kind.value,
            chapter_policy=chapter_policy,
            chapter_policy_digest=chapter_policy_digest,
        )
    if task.task_type not in node.binding.allowed_task_types:
        raise RuntimeError(
            "formal task type does not match the active scene plan binding: "
            f"{task.task_type}"
        )
    return _binding_result(
        task,
        plan=plan,
        node=node,
        policy=policy,
        status="bound",
        node_kind=node.kind.value,
        chapter_policy=chapter_policy,
        chapter_policy_digest=chapter_policy_digest,
    )


def _binding_result(
    task: TaskPackage,
    *,
    plan: CreativeExecutionPlan,
    node: CompiledTaskNode | None,
    policy: SceneExecutionPolicy,
    status: str,
    node_kind: str,
    chapter_policy: ChapterWindowPolicy | None,
    chapter_policy_digest: str,
) -> SceneTaskPlanBinding:
    return SceneTaskPlanBinding(
        task=_bind_payload(
            task,
            plan,
            node,
            policy,
            status,
            chapter_policy=chapter_policy,
            chapter_policy_digest=chapter_policy_digest,
        ),
        status=status,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        node_id=node.node_id if node is not None else "",
        node_kind=node_kind,
        policy=policy,
    )


def _validate_chain(
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    current_project_fingerprint: str,
) -> None:
    if not current_project_fingerprint.strip():
        raise ValueError("current project fingerprint is required")
    if plan.base_project_fingerprint != current_project_fingerprint:
        raise RuntimeError("active scene plan is stale for the current project")
    if (
        graph.plan_id != plan.plan_id
        or graph.plan_revision != plan.revision
        or graph.base_project_fingerprint != plan.base_project_fingerprint
    ):
        raise RuntimeError("compiled graph does not belong to the active scene plan")
    if compiled_graph_digest(graph) != graph.graph_digest:
        raise RuntimeError("compiled scene plan graph digest is invalid")


def _scene_refs(plan: CreativeExecutionPlan) -> set[str]:
    refs = set(plan.scope.scene_ids)
    refs.update(item.scene_ref for item in plan.strategy.scene_inventory)
    refs.update(
        ref
        for node in plan.task_nodes
        for ref in node.scope_refs
        if ref.startswith("scene_")
    )
    if plan.scope.kind.value == "scene":
        refs.add(plan.scope.key)
    return refs


def _scene_policy(
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    scene_id: str,
    *,
    chapter_policy: ChapterWindowPolicy | None,
) -> SceneExecutionPolicy:
    scene_strategy = next(
        (item for item in plan.strategy.scene_inventory if item.scene_ref == scene_id),
        None,
    )
    roleplay_node = _single_node(graph, scene_id, PlanNodeKind.ROLEPLAY_SIMULATION)
    roleplay_parameters = _parameters(roleplay_node)
    depth = str(
        roleplay_parameters.get("roleplay_depth")
        or (scene_strategy.roleplay_depth.value if scene_strategy else "targeted")
    )
    branch_node = _single_node(graph, scene_id, PlanNodeKind.BRANCH_SIMULATION)
    branch_count = int(_parameters(branch_node).get("branch_count") or plan.strategy.branch_count)
    if chapter_policy is not None:
        minimum_depth, minimum_branches = chapter_scene_minimums(
            chapter_policy,
            scene_id,
        )
        depth = stronger_roleplay_depth(depth, minimum_depth)
        branch_count = max(branch_count, minimum_branches)
    if depth not in {"light", "targeted", "full"}:
        raise RuntimeError("compiled roleplay depth is invalid")
    if not 2 <= branch_count <= 5:
        raise RuntimeError("compiled branch count is outside the formal Engine range")
    return SceneExecutionPolicy(
        scene_id=scene_id,
        roleplay_depth=depth,
        branch_count=branch_count,
        revision_policy=plan.strategy.revision_policy.value,
        fallback_level=plan.strategy.fallback_level.value,
        narrative_distance=plan.strategy.narrative_distance,
    )


def _resolve_node(
    task: TaskPackage,
    graph: CompiledTaskGraph,
    scene_id: str,
    kind: PlanNodeKind,
) -> CompiledTaskNode | None:
    candidates = [
        node
        for node in graph.nodes
        if node.kind is kind and scene_id in node.scope_refs
    ]
    if kind is PlanNodeKind.SEMANTIC_REVIEW and len(candidates) > 1:
        revision_ids = {
            node.node_id for node in graph.nodes if node.kind is PlanNodeKind.REVISION
        }
        wants_revision = any(
            str(task.payload.get(key) or "").replace("\\", "/").startswith(
                "drafts/revisions/"
            )
            for key in ("candidate", "revision_source")
        )
        filtered = [
            node
            for node in candidates
            if bool(revision_ids.intersection(node.dependencies)) is wants_revision
        ]
        if filtered:
            candidates = filtered
    if not candidates:
        return None
    if len(candidates) != 1:
        raise RuntimeError(
            "active scene plan cannot bind the formal task unambiguously: "
            f"{kind.value} has {len(candidates)} candidates"
        )
    return candidates[0]


def _single_node(
    graph: CompiledTaskGraph,
    scene_id: str,
    kind: PlanNodeKind,
) -> CompiledTaskNode:
    candidates = [
        node
        for node in graph.nodes
        if node.kind is kind and scene_id in node.scope_refs
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"active scene plan requires exactly one {kind.value} node for {scene_id}"
        )
    return candidates[0]


def _parameters(node: CompiledTaskNode) -> dict[str, str | int | float | bool]:
    return {item.name: item.value for item in node.parameters}


def _bind_payload(
    task: TaskPackage,
    plan: CreativeExecutionPlan,
    node: CompiledTaskNode | None,
    policy: SceneExecutionPolicy,
    status: str,
    *,
    chapter_policy: ChapterWindowPolicy | None,
    chapter_policy_digest: str,
) -> TaskPackage:
    payload = dict(task.payload)
    payload.update(
        {
            "creative_plan_id": plan.plan_id,
            "creative_plan_revision": plan.revision,
            "creative_plan_binding_status": status,
            "creative_scene_policy": policy.as_dict(),
        }
    )
    if node is not None:
        payload["creative_plan_node_id"] = node.node_id
        payload["creative_plan_node_kind"] = node.kind.value
        payload["creative_plan_required_gates"] = list(node.binding.required_gate_ids)
        payload["creative_plan_agent_role"] = node.binding.agent_role
    if chapter_policy is not None:
        if not chapter_policy_digest:
            raise ValueError("chapter policy digest is required for production binding")
        payload["creative_chapter_policy"] = chapter_policy.as_dict()
        payload["creative_chapter_policy_digest"] = chapter_policy_digest
    constraints = [
        *[str(item) for item in payload.get("hard_constraints") or []],
        *_policy_constraints(task.current_state, policy),
    ]
    payload["hard_constraints"] = list(dict.fromkeys(item for item in constraints if item))
    payload["command"] = _bound_command(str(payload.get("command") or ""), task.current_state, policy)
    return replace(task, payload=payload)


def _policy_constraints(
    current_state: str,
    policy: SceneExecutionPolicy,
) -> tuple[str, ...]:
    common = (
        "This task is bound to an active, machine-validated scene plan; do not weaken or reinterpret its strategy values.",
    )
    if current_state in {"roleplay-simulation", "roleplay-agent-task"}:
        return (
            *common,
            f"RP depth is {policy.roleplay_depth}; light remains a complete causal check and never waives formal RP evidence.",
        )
    if current_state in {"branch-manifest", "branch-agent-task", "branch-selection"}:
        return (*common, f"Create and evaluate exactly {policy.branch_count} branch candidates.")
    if current_state in {"candidate-generation-provenance", "generation-agent-task"}:
        return (
            *common,
            f"Use narrative distance policy: {policy.narrative_distance}.",
        )
    if current_state in {
        "candidate-revision",
        "candidate-human-decision",
        "static-revision",
    }:
        return (
            *common,
            f"Revision policy is {policy.revision_policy}; fallback level is {policy.fallback_level}.",
            "A fallback changes the next plan revision or formal route position; it never authorizes skipping fresh review.",
        )
    return common


def _bound_command(
    command: str,
    current_state: str,
    policy: SceneExecutionPolicy,
) -> str:
    if not command:
        return command
    if current_state == "roleplay-simulation" and "--roleplay-depth" not in command:
        return f"{command} --roleplay-depth {policy.roleplay_depth}"
    if current_state == "branch-manifest" and "--branch-count" not in command:
        return f"{command} --branch-count {policy.branch_count}"
    return command
