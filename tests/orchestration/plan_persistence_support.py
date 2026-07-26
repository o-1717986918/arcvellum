from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.orchestration import (
    FreedomBudget,
    FormalTaskObservation,
    FormalTaskStatus,
    NormalizationContext,
    PlanLintContext,
    PlanSimulationContext,
    compile_plan,
    lint_plan,
    normalize_plan_candidate,
    parse_plan_candidate,
    simulate_plan,
)
from literary_engineering_studio.runtime.resources import ResourceClaim

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate


FINGERPRINT = "project-revision-1"
PROJECT_ID = "project-test"


def shadow_pipeline(candidate_payload=None, *, plan_id: str = ""):
    candidate = candidate_payload or scene_plan_candidate()
    budget = FreedomBudget(**freedom_budget())
    plan = normalize_plan_candidate(
        parse_plan_candidate(candidate),
        context=NormalizationContext(
            base_project_fingerprint=FINGERPRINT,
            approved_budget=budget,
            plan_id=plan_id,
            created_at="2026-07-26T00:00:00+00:00",
        ),
    )
    lint_result = lint_plan(
        plan,
        context=PlanLintContext(
            current_project_fingerprint=FINGERPRINT,
            known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
            allowed_capability_ids=frozenset({"project.query"}),
            authorized_budget=budget,
        ),
    )
    graph = compile_plan(plan, lint_result=lint_result)
    observations, claims = observations_and_claims(graph)
    simulation = simulate_plan(
        graph,
        context=PlanSimulationContext(
            current_project_fingerprint=FINGERPRINT,
            project_id=PROJECT_ID,
            task_observations=observations,
            resource_claims=claims,
        ),
    )
    return candidate, plan, graph, lint_result, simulation


def simulation_context_for_graph(graph) -> PlanSimulationContext:
    observations, claims = observations_and_claims(graph)
    return PlanSimulationContext(
        current_project_fingerprint=FINGERPRINT,
        project_id=PROJECT_ID,
        task_observations=observations,
        resource_claims=claims,
    )


def observations_and_claims(graph):
    observations = tuple(
        FormalTaskObservation(
            node_id=node.node_id,
            status=FormalTaskStatus.PROJECTED,
            route=node.binding.route,
            task_type=node.binding.allowed_task_types[0],
            scope_refs=node.scope_refs,
            base_project_fingerprint=FINGERPRINT,
            expected_outputs=(f"artifacts/{node.node_id}.json",),
        )
        for node in graph.nodes
    )
    claims = tuple(
        ResourceClaim(
            task_node_id=node.node_id,
            project_id=PROJECT_ID,
            reads=(),
            writes=(f"artifacts/{node.node_id}.json",),
            runtime_slot="agent-worker",
            model_slot="default",
            network="none",
            exclusive_barriers=(),
        )
        for node in graph.nodes
    )
    return observations, claims


def index_record(
    plan_id: str,
    *,
    project_root: Path | str,
    review_status: str = "pass",
    materialize: bool = True,
) -> dict:
    root = Path(project_root)
    references: dict[str, dict[str, str]] = {}
    for field in ("candidate", "normalized", "compiled", "lint", "simulation", "review"):
        relative = (
            Path("workflow")
            / "orchestration"
            / "test-audits"
            / plan_id
            / f"{field}.json"
        )
        text = json.dumps({"field": field, "plan_id": plan_id}, sort_keys=True) + "\n"
        digest = _materialize_reference(root, relative, text) if materialize else _hash(text)
        references[field] = {"path": relative.as_posix(), "sha256": digest}
    return {
        "plan_id": plan_id,
        "revision": 1,
        "project_root": str(project_root),
        "scope_kind": "scene",
        "scope_key": "scene_0001",
        "status": "shadow",
        "base_project_fingerprint": FINGERPRINT,
        "policy": {"max_replans": 1},
        "candidate": references["candidate"],
        "normalized": references["normalized"],
        "compiled": references["compiled"],
        "lint": {**references["lint"], "status": "pass"},
        "simulation": {**references["simulation"], "status": "pass"},
        "review": {**references["review"], "status": review_status},
        "digest": record_digest(plan_id),
        "created_at": "2026-07-26T00:00:00+00:00",
    }


def persist_ready_record(
    store: JobStore,
    project_root: Path,
    plan_id: str,
    *,
    review_status: str = "pass",
) -> dict:
    record = index_record(
        plan_id,
        project_root=project_root,
        review_status=review_status,
    )
    reserved = store.reserve_creative_plan_revision(record)
    return store.finalize_creative_plan_revision(
        plan_id,
        1,
        digest=reserved["digest"],
    )


def active_projection_args(
    project_root: Path,
    plan_id: str,
    *,
    revision_digest: str | None = None,
) -> dict:
    return {
        "active_plan_path": (
            project_root / "workflow" / "orchestration" / "active_plan.json"
        ),
        "active_plan_payload": {
            "schema": "arcvellum/active-creative-plan/v1",
            "plan_id": plan_id,
            "revision": 1,
            "revision_digest": revision_digest or record_digest(plan_id),
            "base_project_fingerprint": FINGERPRINT,
        },
    }


def record_digest(plan_id: str) -> str:
    return hashlib.sha256(plan_id.encode("utf-8")).hexdigest()


class FailingCommitConnection:
    def __init__(self, connection):
        self._connection = connection

    def commit(self):
        raise sqlite3.OperationalError("commit failed")

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _materialize_reference(root: Path, relative: Path, text: str) -> str:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
