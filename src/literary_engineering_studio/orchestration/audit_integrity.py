"""Semantic integrity checks across persisted orchestration audit artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .candidate import parse_plan_candidate
from .compiler import compiled_graph_digest
from .contracts import CompiledTaskGraph, CreativeExecutionPlan, to_primitive
from .lint import PlanLintResult
from .normalizer import candidate_digest
from .simulator import PlanSimulationResult


def validate_revision_chain(
    candidate_payload: dict[str, Any],
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
) -> None:
    parsed = parse_plan_candidate(candidate_payload)
    if candidate_digest(parsed.candidate) != plan.candidate_digest:
        raise ValueError("candidate payload does not belong to the normalized plan")
    if graph.plan_id != plan.plan_id or graph.plan_revision != plan.revision:
        raise ValueError("compiled graph does not belong to the plan revision")
    if graph.base_project_fingerprint != plan.base_project_fingerprint:
        raise ValueError("compiled graph project fingerprint does not match the plan")
    if graph.graph_digest != compiled_graph_digest(graph):
        raise ValueError("compiled graph digest does not match its graph payload")
    if lint_result.plan_digest != canonical_json_digest(to_primitive(plan)):
        raise ValueError("Plan Lint receipt does not match the persisted plan")
    _validate_simulation(plan, graph, simulation)


def verify_semantic_chain(
    payloads: dict[str, dict[str, Any]],
    provenance: dict[str, Any],
) -> None:
    candidate = payloads["candidate"]
    plan = payloads["normalized"]
    graph = payloads["compiled"]
    lint = payloads["lint"]
    simulation = payloads["simulation"]
    _verify_candidate_plan(candidate, plan)
    plan_digest = _verify_plan_lint(plan, lint)
    graph_digest, identity = _verify_graph(plan, graph)
    _verify_simulation_payload(simulation, graph_digest, identity[2])
    _verify_provenance(provenance, identity, plan_digest, graph_digest)


def canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_simulation(
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    simulation: PlanSimulationResult,
) -> None:
    if simulation.graph_digest != graph.graph_digest:
        raise ValueError("Plan Simulation does not belong to the compiled graph")
    if simulation.base_project_fingerprint != plan.base_project_fingerprint:
        raise ValueError("Plan Simulation project fingerprint does not match the plan")


def _verify_candidate_plan(
    candidate: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    source_digest = candidate_digest(parse_plan_candidate(candidate).candidate)
    if source_digest != str(plan.get("candidate_digest") or ""):
        raise RuntimeError("creative plan candidate does not match the normalized plan")


def _verify_plan_lint(
    plan: dict[str, Any],
    lint: dict[str, Any],
) -> str:
    plan_digest = canonical_json_digest(plan)
    if str(lint.get("plan_digest") or "") != plan_digest:
        raise RuntimeError("creative plan lint receipt does not match the normalized plan")
    return plan_digest


def _verify_graph(
    plan: dict[str, Any],
    graph: dict[str, Any],
) -> tuple[str, tuple[str, int, str]]:
    graph_projection = dict(graph)
    graph_projection["graph_digest"] = ""
    graph_digest = canonical_json_digest(graph_projection)
    if str(graph.get("graph_digest") or "") != graph_digest:
        raise RuntimeError("creative plan compiled graph digest is invalid")
    identity = (
        str(plan.get("plan_id") or ""),
        int(plan.get("revision") or 0),
        str(plan.get("base_project_fingerprint") or ""),
    )
    graph_identity = (
        str(graph.get("plan_id") or ""),
        int(graph.get("plan_revision") or 0),
        str(graph.get("base_project_fingerprint") or ""),
    )
    if identity != graph_identity:
        raise RuntimeError("creative plan compiled graph belongs to another plan revision")
    return graph_digest, identity


def _verify_simulation_payload(
    simulation: dict[str, Any],
    graph_digest: str,
    project_fingerprint: str,
) -> None:
    if graph_digest != str(simulation.get("graph_digest") or ""):
        raise RuntimeError("creative plan simulation belongs to another graph")
    if project_fingerprint != str(simulation.get("base_project_fingerprint") or ""):
        raise RuntimeError("creative plan simulation belongs to another project revision")


def _verify_provenance(
    provenance: dict[str, Any],
    identity: tuple[str, int, str],
    plan_digest: str,
    graph_digest: str,
) -> None:
    observed = (
        str(provenance.get("plan_id") or ""),
        int(provenance.get("revision") or 0),
        str(provenance.get("base_project_fingerprint") or ""),
        str(provenance.get("plan_digest") or ""),
        str(provenance.get("graph_digest") or ""),
    )
    if observed != (*identity, plan_digest, graph_digest):
        raise RuntimeError("creative plan provenance semantic chain is inconsistent")
