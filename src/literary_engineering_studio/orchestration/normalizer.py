"""Bind machine-owned plan identity, budgets, and mandatory Gate sets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import re
from typing import Mapping

from literary_engineering_studio_engine.orchestration import mandatory_gates_for

from ..protocols.canonical_json import canonical_json_digest
from .constitution import constitution_v1
from .contracts import (
    PLAN_SCHEMA,
    CandidateParseResult,
    CreativeExecutionPlan,
    CreativeExecutionPlanCandidate,
    CreativeStrategy,
    FreedomBudget,
    PlanGateBinding,
    PlanLifecycleStatus,
    PlanTaskNode,
    to_primitive,
)
from .scene_strategy_policy import project_scene_strategy_parameters


@dataclass(frozen=True)
class NormalizationContext:
    base_project_fingerprint: str
    approved_budget: FreedomBudget
    revision: int = 1
    plan_id: str = ""
    created_at: str = ""
    risk_features_by_node: Mapping[str, Mapping[str, bool]] | None = None


def normalize_plan_candidate(
    parsed: CandidateParseResult,
    *,
    context: NormalizationContext,
) -> CreativeExecutionPlan:
    fingerprint = context.base_project_fingerprint.strip()
    if not fingerprint:
        raise ValueError("base_project_fingerprint is required")
    if context.revision < 1:
        raise ValueError("plan revision must be positive")
    nodes, node_warnings = _normalize_nodes(parsed.candidate.task_nodes)
    approved_budget, budget_warnings = _clamp_budget(
        parsed.candidate.freedom_request,
        context.approved_budget,
    )
    strategy, strategy_warnings = _normalize_strategy(
        parsed.candidate.strategy,
        approved_budget,
    )
    risk_by_node = context.risk_features_by_node or {}
    nodes, parameter_warnings = project_scene_strategy_parameters(
        nodes,
        strategy=strategy,
        risk_features_by_node=risk_by_node,
    )
    source_digest = candidate_digest(parsed.candidate)
    identity_digest = _digest(
        {"candidate_digest": source_digest, "project_fingerprint": fingerprint}
    )
    plan_id = context.plan_id.strip() or f"plan-{identity_digest[:16]}"
    if not re.fullmatch(r"plan-[a-z0-9-]+", plan_id):
        raise ValueError("plan_id must use the machine plan slug format")
    gate_bindings = tuple(
        PlanGateBinding(
            node_id=node.node_id,
            gate_ids=mandatory_gates_for(
                node_kind=node.kind.value,
                risk_features=risk_by_node.get(node.node_id),
            ),
        )
        for node in nodes
    )
    return CreativeExecutionPlan(
        schema=PLAN_SCHEMA,
        plan_id=plan_id,
        revision=context.revision,
        base_project_fingerprint=fingerprint,
        candidate_digest=source_digest,
        constitution_version=constitution_v1().version,
        created_at=context.created_at or datetime.now(timezone.utc).isoformat(),
        lifecycle_status=PlanLifecycleStatus.NORMALIZED,
        scope=parsed.candidate.scope,
        objective=parsed.candidate.objective,
        interpretation=parsed.candidate.interpretation,
        strategy=strategy,
        task_nodes=nodes,
        replan_rules=parsed.candidate.replan_rules,
        freedom_budget=approved_budget,
        route_macro_id="explicit-task-graph.v1",
        route_sequence=(),
        mandatory_gate_nodes=gate_bindings,
        candidate_warnings=tuple(
            dict.fromkeys(
                [
                    *parsed.warnings,
                    *node_warnings,
                    *budget_warnings,
                    *strategy_warnings,
                    *parameter_warnings,
                ]
            )
        ),
    )


def _normalize_nodes(
    nodes: tuple[PlanTaskNode, ...],
) -> tuple[tuple[PlanTaskNode, ...], tuple[str, ...]]:
    source_ids = [node.node_id for node in nodes]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("candidate task node IDs must be unique before normalization")
    id_map = {node_id: _node_slug(node_id) for node_id in source_ids}
    if len(set(id_map.values())) != len(id_map):
        raise ValueError("candidate task node IDs collide after normalization")
    warnings = tuple(
        f"node id normalized: {source} -> {normalized}"
        for source, normalized in id_map.items()
        if source != normalized
    )
    normalized_nodes = tuple(
        replace(
            node,
            node_id=id_map[node.node_id],
            depends_on=tuple(id_map.get(item, _node_slug(item)) for item in node.depends_on),
            scope_refs=tuple(dict.fromkeys(item.strip() for item in node.scope_refs if item.strip())),
            requested_capabilities=tuple(
                sorted({item.strip() for item in node.requested_capabilities if item.strip()})
            ),
        )
        for node in nodes
    )
    return normalized_nodes, warnings


def _clamp_budget(
    requested: FreedomBudget,
    approved: FreedomBudget,
) -> tuple[FreedomBudget, tuple[str, ...]]:
    fields = (
        "max_added_tasks",
        "max_replans_per_scope",
        "max_parallel_read_tasks",
        "max_branch_count",
        "max_research_tasks",
        "max_research_cost",
        "max_analysis_to_production_ratio",
        "max_plan_depth",
        "max_plan_stall_cycles",
    )
    values = {name: min(getattr(requested, name), getattr(approved, name)) for name in fields}
    normalized = FreedomBudget(**values)
    warnings = tuple(
        f"freedom request clamped by policy: {name}"
        for name in fields
        if getattr(requested, name) != getattr(normalized, name)
    )
    return normalized, warnings


def _normalize_strategy(
    strategy: CreativeStrategy,
    budget: FreedomBudget,
) -> tuple[CreativeStrategy, tuple[str, ...]]:
    branch_count = max(1, min(strategy.branch_count, budget.max_branch_count, 5))
    warnings = (
        ("strategy branch_count clamped by approved Freedom Budget",)
        if branch_count != strategy.branch_count
        else ()
    )
    return replace(strategy, branch_count=branch_count), warnings


def _node_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("task node id cannot normalize to an empty slug")
    return slug[:64]


def _digest(payload: object) -> str:
    return canonical_json_digest(payload)


def candidate_digest(candidate: CreativeExecutionPlanCandidate) -> str:
    return _digest(to_primitive(candidate))
