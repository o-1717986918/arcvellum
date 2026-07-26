"""Side-effect-free simulation of a sealed task graph against formal state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from literary_engineering_studio.runtime.resources import (
    ResourceClaim,
    claims_conflict,
)

from .compiler import compiled_graph_digest
from .contracts import CompiledTaskGraph, CompiledTaskNode
from .lint import PlanIssue, PlanIssueSeverity


class FormalTaskStatus(str, Enum):
    PROJECTED = "projected"
    AVAILABLE = "available"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FormalTaskObservation:
    node_id: str
    status: FormalTaskStatus
    route: str
    task_type: str
    scope_refs: tuple[str, ...]
    base_project_fingerprint: str
    source_paths: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    blocker: str = ""


@dataclass(frozen=True)
class PlanSimulationContext:
    current_project_fingerprint: str
    project_id: str
    task_observations: tuple[FormalTaskObservation, ...]
    resource_claims: tuple[ResourceClaim, ...]
    stale_invalidations: tuple[str, ...] = ()
    model_call_cost_range: tuple[float, float] = (0.0, 0.0)
    model_call_runtime_range_seconds: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class SimulatedNode:
    node_id: str
    status: str
    blockers: tuple[str, ...]
    expected_outputs: tuple[str, ...]


@dataclass(frozen=True)
class SimulatedResourceConflict:
    left_node_id: str
    right_node_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PlanSimulationResult:
    status: str
    graph_digest: str
    base_project_fingerprint: str
    resolved_nodes: tuple[SimulatedNode, ...]
    injected_nodes: tuple[str, ...]
    blocking_issues: tuple[PlanIssue, ...]
    warnings: tuple[PlanIssue, ...]
    resource_conflicts: tuple[SimulatedResourceConflict, ...]
    expected_artifacts: tuple[str, ...]
    stale_invalidations: tuple[str, ...]
    estimated_model_calls: int
    estimated_cost_range: tuple[float, float]
    estimated_runtime_range_seconds: tuple[int, int]

    @property
    def passed(self) -> bool:
        return self.status != "fail"


def simulate_plan(
    graph: CompiledTaskGraph,
    *,
    context: PlanSimulationContext,
) -> PlanSimulationResult:
    issues: list[PlanIssue] = []
    warnings: list[PlanIssue] = []
    if graph.base_project_fingerprint != context.current_project_fingerprint:
        issues.append(_issue("stale-compiled-graph", "compiled graph targets a stale project revision"))
    if graph.graph_digest != compiled_graph_digest(graph):
        issues.append(_issue("compiled-graph-integrity", "compiled graph digest does not match its content"))
    if graph.route_macro_id == "fixed-formal-route.v1":
        return _fixed_result(graph, issues, context)
    observations = {item.node_id: item for item in context.task_observations}
    claims = {item.task_node_id: item for item in context.resource_claims}
    resolved = _resolve_nodes(graph, context, observations, claims, issues)
    conflicts = _resource_conflicts(graph, claims)
    expected_artifacts = _expected_artifacts(graph, observations)
    _detect_unconsumed_outputs(graph, observations, warnings)
    _detect_no_progress(graph, issues)
    if conflicts:
        issues.append(_issue("resource-conflict", "parallel task nodes have conflicting resources"))
    model_calls = sum(_uses_model(node) for node in graph.nodes)
    cost_range = tuple(value * model_calls for value in context.model_call_cost_range)
    runtime_range = tuple(value * model_calls for value in context.model_call_runtime_range_seconds)
    status = "fail" if issues else ("warn" if warnings else "pass")
    return PlanSimulationResult(
        status=status,
        graph_digest=graph.graph_digest,
        base_project_fingerprint=graph.base_project_fingerprint,
        resolved_nodes=resolved,
        injected_nodes=tuple(
            node.node_id
            for node in graph.nodes
            if node.dependencies != node.declared_dependencies
        ),
        blocking_issues=tuple(issues),
        warnings=tuple(warnings),
        resource_conflicts=conflicts,
        expected_artifacts=expected_artifacts,
        stale_invalidations=tuple(dict.fromkeys(context.stale_invalidations)),
        estimated_model_calls=model_calls,
        estimated_cost_range=(float(cost_range[0]), float(cost_range[1])),
        estimated_runtime_range_seconds=(int(runtime_range[0]), int(runtime_range[1])),
    )


def _fixed_result(
    graph: CompiledTaskGraph,
    issues: list[PlanIssue],
    context: PlanSimulationContext,
) -> PlanSimulationResult:
    return PlanSimulationResult(
        status="fail" if issues else "pass",
        graph_digest=graph.graph_digest,
        base_project_fingerprint=graph.base_project_fingerprint,
        resolved_nodes=(),
        injected_nodes=(),
        blocking_issues=tuple(issues),
        warnings=(),
        resource_conflicts=(),
        expected_artifacts=(),
        stale_invalidations=tuple(dict.fromkeys(context.stale_invalidations)),
        estimated_model_calls=0,
        estimated_cost_range=(0.0, 0.0),
        estimated_runtime_range_seconds=(0, 0),
    )


def _resolve_nodes(
    graph: CompiledTaskGraph,
    context: PlanSimulationContext,
    observations: dict[str, FormalTaskObservation],
    claims: dict[str, ResourceClaim],
    issues: list[PlanIssue],
) -> tuple[SimulatedNode, ...]:
    statuses: dict[str, str] = {}
    resolved: list[SimulatedNode] = []
    for node in graph.nodes:
        observation = observations.get(node.node_id)
        blockers = _observation_blockers(node, graph, context, observation, claims.get(node.node_id))
        dependency_blocked = any(statuses.get(item) == "blocked" for item in node.dependencies)
        if dependency_blocked:
            blockers.append("a dependency is blocked")
        if blockers:
            status = "blocked"
            issues.append(_issue("formal-task-binding", "; ".join(blockers), (node.node_id,)))
        elif observation and observation.status == FormalTaskStatus.COMPLETED:
            status = "completed"
        elif all(statuses.get(item) == "completed" for item in node.dependencies):
            status = "ready"
        else:
            status = "waiting"
        statuses[node.node_id] = status
        resolved.append(
            SimulatedNode(
                node_id=node.node_id,
                status=status,
                blockers=tuple(blockers),
                expected_outputs=observation.expected_outputs if observation else (),
            )
        )
    return tuple(resolved)


def _observation_blockers(
    node: CompiledTaskNode,
    graph: CompiledTaskGraph,
    context: PlanSimulationContext,
    observation: FormalTaskObservation | None,
    claim: ResourceClaim | None,
) -> list[str]:
    if observation is None:
        return ["formal task observation is missing"]
    blockers: list[str] = []
    if observation.status == FormalTaskStatus.BLOCKED:
        blockers.append(observation.blocker or "formal task is blocked")
    if observation.route != node.binding.route:
        blockers.append("formal route does not match compiled binding")
    if observation.task_type not in node.binding.allowed_task_types:
        blockers.append("formal task type is not allowed by compiled binding")
    if observation.base_project_fingerprint != graph.base_project_fingerprint:
        blockers.append("formal task targets a different project revision")
    if observation.scope_refs and not set(node.scope_refs).issubset(observation.scope_refs):
        blockers.append("formal task scope does not cover the compiled node")
    if claim is None:
        blockers.append("resource claim is missing")
    elif claim.project_id != context.project_id:
        blockers.append("resource claim targets a different project")
    return blockers


def _resource_conflicts(
    graph: CompiledTaskGraph,
    claims: dict[str, ResourceClaim],
) -> tuple[SimulatedResourceConflict, ...]:
    dependencies = {node.node_id: node.dependencies for node in graph.nodes}
    result: list[SimulatedResourceConflict] = []
    for index, left in enumerate(graph.nodes):
        for right in graph.nodes[index + 1 :]:
            if _ordered(left.node_id, right.node_id, dependencies):
                continue
            left_claim = claims.get(left.node_id)
            right_claim = claims.get(right.node_id)
            if left_claim is None or right_claim is None:
                continue
            conflict = claims_conflict(left_claim, right_claim)
            if conflict.conflicts:
                result.append(
                    SimulatedResourceConflict(
                        left_node_id=left.node_id,
                        right_node_id=right.node_id,
                        reasons=conflict.reasons,
                    )
                )
    return tuple(result)


def _ordered(
    left: str,
    right: str,
    dependencies: dict[str, tuple[str, ...]],
) -> bool:
    return left in _ancestors(right, dependencies) or right in _ancestors(left, dependencies)


def _ancestors(node_id: str, dependencies: dict[str, tuple[str, ...]]) -> set[str]:
    found: set[str] = set()
    pending = list(dependencies.get(node_id, ()))
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(dependencies.get(current, ()))
    return found


def _expected_artifacts(
    graph: CompiledTaskGraph,
    observations: dict[str, FormalTaskObservation],
) -> tuple[str, ...]:
    values: list[str] = []
    for node in graph.nodes:
        observation = observations.get(node.node_id)
        values.extend(observation.expected_outputs if observation else ())
        values.extend(node.progress_contract.formal_artifact_delta)
        if node.progress_contract.expected_state_patch:
            values.append(node.progress_contract.expected_state_patch)
    return tuple(dict.fromkeys(values))


def _detect_unconsumed_outputs(
    graph: CompiledTaskGraph,
    observations: dict[str, FormalTaskObservation],
    warnings: list[PlanIssue],
) -> None:
    terminal_ids = {node.node_id for node in graph.nodes}
    for node in graph.nodes:
        for dependency in node.dependencies:
            terminal_ids.discard(dependency)
    all_sources = {path for item in observations.values() for path in item.source_paths}
    formal = {
        path
        for node in graph.nodes
        for path in node.progress_contract.formal_artifact_delta
    }
    for node in graph.nodes:
        observation = observations.get(node.node_id)
        if observation is None or node.node_id in terminal_ids:
            continue
        unused = tuple(path for path in observation.expected_outputs if path not in all_sources | formal)
        if unused:
            warnings.append(
                _issue(
                    "unconsumed-output",
                    "task outputs are not consumed by a downstream observation",
                    (node.node_id, *unused),
                    PlanIssueSeverity.WARNING,
                )
            )


def _detect_no_progress(
    graph: CompiledTaskGraph,
    issues: list[PlanIssue],
) -> None:
    has_progress = any(
        node.progress_contract.formal_artifact_delta
        or node.progress_contract.expected_state_patch
        or node.binding.progress_kind == "release"
        for node in graph.nodes
    )
    if graph.nodes and not has_progress:
        issues.append(_issue("no-formal-progress", "plan has no verifiable formal artifact or state delta"))


def _uses_model(node: CompiledTaskNode) -> int:
    return int(node.binding.agent_role not in {"deterministic-engine", "human-decision"})


def _issue(
    code: str,
    message: str,
    node_ids: tuple[str, ...] = (),
    severity: PlanIssueSeverity = PlanIssueSeverity.ERROR,
) -> PlanIssue:
    return PlanIssue(code=code, severity=severity, message=message, node_ids=node_ids)
