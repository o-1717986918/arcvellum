"""Compile validated creative plans into sealed, command-free task bindings."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

from literary_engineering_studio_engine.orchestration import (
    PlanNodeKind,
    check_default_plan_compatibility,
)

from .compiler_registry import CompilerRegistry
from .contracts import (
    COMPILED_GRAPH_SCHEMA,
    CompiledTaskGraph,
    CompiledTaskNode,
    CreativeExecutionPlan,
    PlanTaskNode,
    to_primitive,
)
from .lint import PlanLintResult


class PlanCompilationError(ValueError):
    pass


_SERIAL_MUTATION_KINDS = frozenset(
    {
        PlanNodeKind.STATE_EVOLUTION,
        PlanNodeKind.CANON_EVOLUTION,
        PlanNodeKind.EXPORT,
    }
)


def compile_plan(
    plan: CreativeExecutionPlan,
    *,
    lint_result: PlanLintResult,
    registry: CompilerRegistry | None = None,
) -> CompiledTaskGraph:
    if not lint_result.passed:
        raise PlanCompilationError("plan cannot compile while Plan Lint has errors")
    if lint_result.plan_digest != _digest(plan):
        raise PlanCompilationError("Plan Lint result does not match the current plan revision")
    resolved_registry = registry or CompilerRegistry()
    if plan.route_macro_id == "fixed-formal-route.v1":
        return _compile_fixed(plan, resolved_registry)
    if plan.route_macro_id != "explicit-task-graph.v1":
        raise PlanCompilationError(f"unsupported route macro: {plan.route_macro_id}")
    ordered = _topological_order(plan)
    effective_dependencies = _serialized_dependencies(ordered)
    gates_by_node = {
        binding.node_id: binding.gate_ids for binding in plan.mandatory_gate_nodes
    }
    nodes = tuple(
        CompiledTaskNode(
            node_id=node.node_id,
            kind=node.kind,
            scope_refs=node.scope_refs,
            declared_dependencies=node.depends_on,
            dependencies=effective_dependencies[node.node_id],
            binding=replace(
                resolved_registry.resolve(node),
                required_gate_ids=gates_by_node[node.node_id],
            ),
            requested_capabilities=node.requested_capabilities,
            parameters=node.parameters,
            contribution=node.contribution,
            progress_contract=node.progress_contract,
        )
        for node in ordered
    )
    graph = CompiledTaskGraph(
        schema=COMPILED_GRAPH_SCHEMA,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        base_project_fingerprint=plan.base_project_fingerprint,
        route_macro_id=plan.route_macro_id,
        route_sequence=(),
        nodes=nodes,
        graph_digest="",
    )
    return replace(graph, graph_digest=compiled_graph_digest(graph))


def compiled_graph_digest(graph: CompiledTaskGraph) -> str:
    return _digest(replace(graph, graph_digest=""))


def _compile_fixed(
    plan: CreativeExecutionPlan,
    registry: CompilerRegistry,
) -> CompiledTaskGraph:
    compatibility = check_default_plan_compatibility(
        route_macro_id=plan.route_macro_id,
        route_sequence=plan.route_sequence,
        supported_routes=registry.routes,
    )
    if not compatibility.compatible:
        raise PlanCompilationError("; ".join(compatibility.issues))
    graph = CompiledTaskGraph(
        schema=COMPILED_GRAPH_SCHEMA,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        base_project_fingerprint=plan.base_project_fingerprint,
        route_macro_id=plan.route_macro_id,
        route_sequence=plan.route_sequence,
        nodes=(),
        graph_digest="",
    )
    return replace(graph, graph_digest=compiled_graph_digest(graph))


def _topological_order(plan: CreativeExecutionPlan) -> tuple[PlanTaskNode, ...]:
    by_id = {node.node_id: node for node in plan.task_nodes}
    indegree = {node_id: 0 for node_id in by_id}
    children = {node_id: [] for node_id in by_id}
    for node in plan.task_nodes:
        for dependency in node.depends_on:
            if dependency not in by_id:
                raise PlanCompilationError(f"missing dependency during compile: {dependency}")
            indegree[node.node_id] += 1
            children[dependency].append(node.node_id)
    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    ordered = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(by_id[node_id])
        for child in sorted(children[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(ordered) != len(by_id):
        raise PlanCompilationError("task graph contains a cycle")
    return tuple(ordered)


def _serialized_dependencies(
    nodes: tuple[PlanTaskNode, ...],
) -> dict[str, tuple[str, ...]]:
    effective = {node.node_id: list(node.depends_on) for node in nodes}
    previous_mutation = ""
    for node in nodes:
        if node.kind not in _SERIAL_MUTATION_KINDS:
            continue
        if previous_mutation and previous_mutation not in _ancestors(node.node_id, effective):
            effective[node.node_id].append(previous_mutation)
        previous_mutation = node.node_id
    return {node_id: tuple(dict.fromkeys(values)) for node_id, values in effective.items()}


def _ancestors(node_id: str, dependencies: dict[str, list[str]]) -> set[str]:
    found: set[str] = set()
    pending = list(dependencies.get(node_id, ()))
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(dependencies.get(current, ()))
    return found


def _digest(value: object) -> str:
    payload = to_primitive(value)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
