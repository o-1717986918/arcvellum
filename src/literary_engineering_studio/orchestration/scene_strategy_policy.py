"""Normalize and validate executable scene strategy parameters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from literary_engineering_studio_engine.orchestration import (
    GateId,
    PlanNodeKind,
    mandatory_gates_for,
)

from .contracts import (
    CreativeExecutionPlan,
    CreativeStrategy,
    PlanParameter,
    PlanTaskNode,
    RoleplayDepth,
    SceneStrategy,
)


@dataclass(frozen=True)
class SceneStrategyViolation:
    code: str
    message: str
    node_ids: tuple[str, ...] = ()


def project_scene_strategy_parameters(
    nodes: tuple[PlanTaskNode, ...],
    *,
    strategy: CreativeStrategy,
    risk_features_by_node: Mapping[str, Mapping[str, bool]],
) -> tuple[tuple[PlanTaskNode, ...], tuple[str, ...]]:
    """Project normalized strategy onto executable task-node parameters."""

    scene_strategies = {item.scene_ref: item for item in strategy.scene_inventory}
    projected: list[PlanTaskNode] = []
    warnings: list[str] = []
    for node in nodes:
        updates = _strategy_parameter_updates(
            node,
            strategy=strategy,
            scene_strategies=scene_strategies,
            risk_features=risk_features_by_node.get(node.node_id),
        )
        projected_node, node_warnings = _project_node_parameters(node, updates)
        projected.append(projected_node)
        warnings.extend(node_warnings)
    return tuple(projected), tuple(warnings)


def scene_strategy_violations(
    plan: CreativeExecutionPlan,
) -> tuple[SceneStrategyViolation, ...]:
    """Return machine-readable violations after normalization or mutation."""

    issues: list[SceneStrategyViolation] = []
    if _has_branch_node(plan) and not 2 <= plan.strategy.branch_count <= 5:
        issues.append(
            SceneStrategyViolation(
                code="branch-count",
                message="adaptive scene branch count must be between 2 and 5",
            )
        )
    inventory = {item.scene_ref: item for item in plan.strategy.scene_inventory}
    gates = {item.node_id: set(item.gate_ids) for item in plan.mandatory_gate_nodes}
    for node in plan.task_nodes:
        issue = _node_strategy_violation(
            node,
            plan=plan,
            inventory=inventory,
            gate_ids=gates.get(node.node_id, set()),
        )
        if issue is not None:
            issues.append(issue)
    return tuple(issues)


def _strategy_parameter_updates(
    node: PlanTaskNode,
    *,
    strategy: CreativeStrategy,
    scene_strategies: Mapping[str, SceneStrategy],
    risk_features: Mapping[str, bool] | None,
) -> dict[str, str | int | float | bool]:
    if node.kind == PlanNodeKind.ROLEPLAY_SIMULATION:
        scene = _scene_strategy(node, scene_strategies)
        depth = scene.roleplay_depth if scene is not None else RoleplayDepth.TARGETED
        gates = mandatory_gates_for(
            node_kind=node.kind.value,
            risk_features=risk_features,
        )
        if GateId.FULL_ROLEPLAY.value in gates:
            depth = RoleplayDepth.FULL
        return {"roleplay_depth": depth.value}
    if node.kind == PlanNodeKind.BRANCH_SIMULATION:
        return {"branch_count": strategy.branch_count}
    if node.kind == PlanNodeKind.FORMAL_PROSE:
        updates: dict[str, str | int | float | bool] = {
            "narrative_distance": strategy.narrative_distance
        }
        if node.progress_contract.target_hanzi > 0:
            updates["target_hanzi"] = node.progress_contract.target_hanzi
        return updates
    if node.kind == PlanNodeKind.REVISION:
        return {
            "revision_policy": strategy.revision_policy.value,
            "fallback_level": strategy.fallback_level.value,
        }
    return {}


def _project_node_parameters(
    node: PlanTaskNode,
    updates: Mapping[str, str | int | float | bool],
) -> tuple[PlanTaskNode, tuple[str, ...]]:
    if not updates:
        return node, ()
    current = {item.name: item.value for item in node.parameters}
    changed = sorted(
        name
        for name, value in updates.items()
        if name in current and current[name] != value
    )
    current.update(updates)
    projected = replace(
        node,
        parameters=tuple(
            PlanParameter(name=name, value=value)
            for name, value in sorted(current.items())
        ),
    )
    warnings = tuple(
        f"node parameter replaced by normalized scene strategy: {node.node_id}.{name}"
        for name in changed
    )
    return projected, warnings


def _node_strategy_violation(
    node: PlanTaskNode,
    *,
    plan: CreativeExecutionPlan,
    inventory: Mapping[str, SceneStrategy],
    gate_ids: set[str],
) -> SceneStrategyViolation | None:
    parameters = {item.name: item.value for item in node.parameters}
    if node.kind == PlanNodeKind.ROLEPLAY_SIMULATION:
        expected = _expected_roleplay_depth(node, inventory, gate_ids)
        return _parameter_violation(
            node,
            parameters,
            {"roleplay_depth": expected},
            code="roleplay-strategy-binding",
            message="roleplay node does not carry the normalized scene depth",
        )
    if node.kind == PlanNodeKind.BRANCH_SIMULATION:
        return _parameter_violation(
            node,
            parameters,
            {"branch_count": plan.strategy.branch_count},
            code="branch-strategy-binding",
            message="branch node does not carry the normalized scene branch count",
        )
    if node.kind == PlanNodeKind.FORMAL_PROSE:
        return _parameter_violation(
            node,
            parameters,
            {"narrative_distance": plan.strategy.narrative_distance},
            code="prose-strategy-binding",
            message="prose node does not carry the normalized narrative distance",
        )
    if node.kind == PlanNodeKind.REVISION:
        return _parameter_violation(
            node,
            parameters,
            {
                "revision_policy": plan.strategy.revision_policy.value,
                "fallback_level": plan.strategy.fallback_level.value,
            },
            code="revision-strategy-binding",
            message="revision node does not carry the normalized revision and fallback policy",
        )
    return None


def _parameter_violation(
    node: PlanTaskNode,
    parameters: Mapping[str, str | int | float | bool],
    expected: Mapping[str, str | int | float | bool],
    *,
    code: str,
    message: str,
) -> SceneStrategyViolation | None:
    if all(parameters.get(name) == value for name, value in expected.items()):
        return None
    return SceneStrategyViolation(code=code, message=message, node_ids=(node.node_id,))


def _expected_roleplay_depth(
    node: PlanTaskNode,
    inventory: Mapping[str, SceneStrategy],
    gate_ids: set[str],
) -> str:
    scene = _scene_strategy(node, inventory)
    expected = scene.roleplay_depth.value if scene is not None else RoleplayDepth.TARGETED.value
    if GateId.FULL_ROLEPLAY.value in gate_ids:
        return RoleplayDepth.FULL.value
    return expected


def _scene_strategy(
    node: PlanTaskNode,
    strategies: Mapping[str, SceneStrategy],
) -> SceneStrategy | None:
    for scope_ref in node.scope_refs:
        if scope_ref in strategies:
            return strategies[scope_ref]
    if len(strategies) == 1:
        return next(iter(strategies.values()))
    return None


def _has_branch_node(plan: CreativeExecutionPlan) -> bool:
    return any(node.kind == PlanNodeKind.BRANCH_SIMULATION for node in plan.task_nodes)
