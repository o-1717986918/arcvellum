"""Semantic integrity checks across persisted orchestration audit artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .agent_protocol import OrchestrationReviewReceipt
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


def validate_review_chain(
    receipt: OrchestrationReviewReceipt,
    *,
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    lint_result: PlanLintResult,
    simulation: PlanSimulationResult,
    context_ledger_digest: str,
) -> None:
    expected = (
        plan.plan_id,
        plan.revision,
        context_ledger_digest,
        plan.candidate_digest,
        lint_result.plan_digest,
        graph.graph_digest,
        canonical_json_digest(to_primitive(simulation)),
    )
    observed = (
        receipt.plan_id,
        receipt.plan_revision,
        receipt.context_ledger_digest,
        receipt.candidate_digest,
        receipt.plan_digest,
        receipt.graph_digest,
        receipt.simulation_digest,
    )
    if observed != expected:
        raise ValueError("orchestration review receipt does not match the reviewed evidence chain")


def verify_semantic_chain(
    payloads: dict[str, dict[str, Any]],
    provenance: dict[str, Any],
) -> None:
    candidate = payloads["candidate"]
    plan = payloads["normalized"]
    graph = payloads["compiled"]
    lint = payloads["lint"]
    simulation = payloads["simulation"]
    review = payloads["review"]
    _verify_candidate_plan(candidate, plan)
    plan_digest = _verify_plan_lint(plan, lint)
    graph_digest, identity = _verify_graph(plan, graph)
    _verify_simulation_payload(simulation, graph_digest, identity[2])
    _verify_review_payload(
        review,
        plan=plan,
        simulation=simulation,
        identity=identity,
        plan_digest=plan_digest,
        graph_digest=graph_digest,
    )
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


def _verify_review_payload(
    review: dict[str, Any],
    *,
    plan: dict[str, Any],
    simulation: dict[str, Any],
    identity: tuple[str, int, str],
    plan_digest: str,
    graph_digest: str,
) -> None:
    if _text(review, "status") == "not_required_shadow":
        return
    expected = (
        identity[0],
        identity[1],
        _text(plan, "candidate_digest"),
        plan_digest,
        graph_digest,
        canonical_json_digest(simulation),
    )
    observed = (
        _text(review, "plan_id"),
        _integer(review, "plan_revision"),
        _text(review, "candidate_digest"),
        _text(review, "plan_digest"),
        _text(review, "graph_digest"),
        _text(review, "simulation_digest"),
    )
    if observed != expected:
        raise RuntimeError("creative plan review belongs to another evidence chain")
    _verify_review_sessions(review)


def _verify_review_sessions(review: dict[str, Any]) -> None:
    planner = _text(review, "planner_session_id")
    reviewer = _text(review, "reviewer_session_id")
    if not planner or not reviewer or planner == reviewer:
        raise RuntimeError("creative plan review lacks an independent reviewer session")


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


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
