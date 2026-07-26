from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from literary_engineering_studio.orchestration import (
    CompilerRegistry,
    DefaultPlanFactory,
    FreedomBudget,
    FormalTaskObservation,
    FormalTaskStatus,
    NormalizationContext,
    PlanCompilationError,
    PlanLintContext,
    PlanSimulationContext,
    compile_plan,
    lint_plan,
    normalize_plan_candidate,
    parse_plan_candidate,
    simulate_plan,
)
from literary_engineering_studio.runtime.resources import ResourceClaim
from literary_engineering_studio_engine.orchestration import GateId

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate


PROJECT_FINGERPRINT = "project-revision-1"
PROJECT_ID = "project-test"


class PlanCompilerAndSimulatorTests(unittest.TestCase):
    def test_compiler_seals_stable_command_free_bindings(self):
        plan, lint_result = _normalized_and_linted()

        graph = compile_plan(plan, lint_result=lint_result)
        repeated = compile_plan(plan, lint_result=lint_result)
        projection = CompilerRegistry().catalog_projection()

        self.assertEqual(graph, repeated)
        self.assertEqual(len(graph.graph_digest), 64)
        self.assertEqual(graph.nodes[0].node_id, "context")
        self.assertTrue(all(node.binding.allowed_task_types for node in graph.nodes))
        self.assertTrue(all("command" not in item for item in projection))

    def test_compiler_preserves_machine_injected_high_risk_gate(self):
        approved = FreedomBudget(**freedom_budget())
        parsed = parse_plan_candidate(scene_plan_candidate())
        plan = normalize_plan_candidate(
            parsed,
            context=NormalizationContext(
                base_project_fingerprint=PROJECT_FINGERPRINT,
                approved_budget=approved,
                created_at="2026-07-26T00:00:00+00:00",
                risk_features_by_node={"roleplay": {"new_character": True}},
            ),
        )
        lint_result = lint_plan(plan, context=_lint_context(approved))

        graph = compile_plan(plan, lint_result=lint_result)
        roleplay = next(node for node in graph.nodes if node.node_id == "roleplay")

        self.assertIn(GateId.FULL_ROLEPLAY.value, roleplay.binding.required_gate_ids)

    def test_compiler_serializes_parallel_formal_mutation_nodes(self):
        payload = scene_plan_candidate()
        state = deepcopy(payload["task_nodes"][-1])
        canon = deepcopy(state)
        canon["node_id"] = "canon"
        canon["kind"] = "canon_evolution"
        payload["task_nodes"].append(canon)
        plan, lint_result = _normalized_and_linted(payload)

        graph = compile_plan(plan, lint_result=lint_result)
        state_node = next(node for node in graph.nodes if node.node_id == "state")

        self.assertIn("canon", state_node.dependencies)
        self.assertNotIn("canon", state_node.declared_dependencies)

    def test_compiler_rejects_parameters_outside_bound_schema(self):
        payload = scene_plan_candidate()
        payload["task_nodes"][0]["parameters"] = {"unexpected": "value"}
        plan, lint_result = _normalized_and_linted(payload)

        with self.assertRaisesRegex(ValueError, "parameters are not allowed"):
            compile_plan(plan, lint_result=lint_result)

    def test_compiler_rejects_failed_or_stale_lint_receipt(self):
        plan, lint_result = _normalized_and_linted()
        changed = replace(plan, objective="plan changed after lint")

        with self.assertRaisesRegex(PlanCompilationError, "does not match"):
            compile_plan(changed, lint_result=lint_result)

        failed = replace(lint_result, status="fail", issues=(
            replace(
                lint_result.issues[0],
                severity=lint_result.issues[0].severity,
            )
            if lint_result.issues
            else _error_issue()
        ,))
        with self.assertRaisesRegex(PlanCompilationError, "Plan Lint has errors"):
            compile_plan(plan, lint_result=failed)

    def test_fixed_macro_compiles_without_copying_formal_task_lifecycle(self):
        plan = DefaultPlanFactory().create(
            base_project_fingerprint=PROJECT_FINGERPRINT,
            created_at="2026-07-26T00:00:00+00:00",
        )
        lint_result = lint_plan(
            plan,
            context=PlanLintContext(
                current_project_fingerprint=PROJECT_FINGERPRINT,
                known_scope_refs=frozenset(),
                allowed_capability_ids=frozenset(),
                authorized_budget=plan.freedom_budget,
            ),
        )

        graph = compile_plan(plan, lint_result=lint_result)

        self.assertEqual(graph.nodes, ())
        self.assertEqual(graph.route_sequence, plan.route_sequence)
        self.assertEqual(graph.route_macro_id, "fixed-formal-route.v1")

    def test_simulator_resolves_valid_graph_and_estimates_model_work(self):
        plan, lint_result = _normalized_and_linted()
        graph = compile_plan(plan, lint_result=lint_result)
        observations, claims = _observations_and_claims(graph)

        result = simulate_plan(
            graph,
            context=PlanSimulationContext(
                current_project_fingerprint=PROJECT_FINGERPRINT,
                project_id=PROJECT_ID,
                task_observations=observations,
                resource_claims=claims,
                stale_invalidations=("drafts/old.md",),
                model_call_cost_range=(0.1, 0.3),
                model_call_runtime_range_seconds=(2, 5),
            ),
        )

        self.assertTrue(result.passed, result.blocking_issues)
        self.assertEqual(result.status, "pass")
        self.assertGreater(result.estimated_model_calls, 0)
        self.assertIn("drafts/old.md", result.stale_invalidations)
        self.assertFalse(result.resource_conflicts)

    def test_simulator_blocks_parallel_resource_conflict(self):
        payload = scene_plan_candidate()
        asset = deepcopy(payload["task_nodes"][0])
        asset["kind"] = "asset_candidate"
        asset["node_id"] = "asset-a"
        asset_b = deepcopy(asset)
        asset_b["node_id"] = "asset-b"
        payload["task_nodes"][0]["depends_on"] = ["asset-a", "asset-b"]
        payload["task_nodes"] = [asset, asset_b, *payload["task_nodes"]]
        plan, lint_result = _normalized_and_linted(payload)
        graph = compile_plan(plan, lint_result=lint_result)
        observations, claims = _observations_and_claims(
            graph,
            shared_writes={"asset-a", "asset-b"},
        )

        result = simulate_plan(
            graph,
            context=PlanSimulationContext(
                current_project_fingerprint=PROJECT_FINGERPRINT,
                project_id=PROJECT_ID,
                task_observations=observations,
                resource_claims=claims,
            ),
        )

        self.assertFalse(result.passed)
        self.assertEqual(len(result.resource_conflicts), 1)
        self.assertIn("resource-conflict", {item.code for item in result.blocking_issues})

    def test_simulator_rejects_analysis_only_no_progress_plan(self):
        plan, _ = _normalized_and_linted()
        context_node = plan.task_nodes[0]
        reduced = replace(
            plan,
            task_nodes=(context_node,),
            mandatory_gate_nodes=(plan.mandatory_gate_nodes[0],),
        )
        lint_result = lint_plan(reduced, context=_lint_context(reduced.freedom_budget))
        graph = compile_plan(reduced, lint_result=lint_result)
        observations, claims = _observations_and_claims(graph)

        result = simulate_plan(
            graph,
            context=PlanSimulationContext(
                current_project_fingerprint=PROJECT_FINGERPRINT,
                project_id=PROJECT_ID,
                task_observations=observations,
                resource_claims=claims,
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("no-formal-progress", {item.code for item in result.blocking_issues})

    def test_simulator_rejects_tampered_graph_digest(self):
        plan, lint_result = _normalized_and_linted()
        graph = replace(
            compile_plan(plan, lint_result=lint_result),
            graph_digest="0" * 64,
        )
        observations, claims = _observations_and_claims(graph)

        result = simulate_plan(
            graph,
            context=PlanSimulationContext(
                current_project_fingerprint=PROJECT_FINGERPRINT,
                project_id=PROJECT_ID,
                task_observations=observations,
                resource_claims=claims,
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("compiled-graph-integrity", {item.code for item in result.blocking_issues})


def _normalized_and_linted(payload: dict | None = None):
    approved = FreedomBudget(**freedom_budget())
    parsed = parse_plan_candidate(payload or scene_plan_candidate())
    plan = normalize_plan_candidate(
        parsed,
        context=NormalizationContext(
            base_project_fingerprint=PROJECT_FINGERPRINT,
            approved_budget=approved,
            created_at="2026-07-26T00:00:00+00:00",
        ),
    )
    lint_result = lint_plan(plan, context=_lint_context(approved))
    if not lint_result.passed:
        raise AssertionError(lint_result.issues)
    return plan, lint_result


def _lint_context(budget: FreedomBudget) -> PlanLintContext:
    return PlanLintContext(
        current_project_fingerprint=PROJECT_FINGERPRINT,
        known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
        allowed_capability_ids=frozenset({"project.query"}),
        authorized_budget=budget,
    )


def _observations_and_claims(graph, *, shared_writes: set[str] | None = None):
    shared_writes = shared_writes or set()
    observations = []
    claims = []
    output_by_node = {}
    for node in graph.nodes:
        output = (
            "artifacts/shared-analysis.json"
            if node.node_id in shared_writes
            else f"artifacts/{node.node_id}.json"
        )
        sources = tuple(output_by_node[item] for item in node.dependencies)
        output_by_node[node.node_id] = output
        observations.append(
            FormalTaskObservation(
                node_id=node.node_id,
                status=FormalTaskStatus.PROJECTED,
                route=node.binding.route,
                task_type=node.binding.allowed_task_types[0],
                scope_refs=node.scope_refs,
                base_project_fingerprint=PROJECT_FINGERPRINT,
                source_paths=sources,
                expected_outputs=(output,),
            )
        )
        claims.append(
            ResourceClaim(
                task_node_id=node.node_id,
                project_id=PROJECT_ID,
                reads=sources,
                writes=(output,),
                runtime_slot="agent-worker",
                model_slot="default",
                network="none",
                exclusive_barriers=(),
            )
        )
    return tuple(observations), tuple(claims)


def _error_issue():
    from literary_engineering_studio.orchestration import PlanIssue, PlanIssueSeverity

    return PlanIssue("forced", PlanIssueSeverity.ERROR, "forced test failure")


if __name__ == "__main__":
    unittest.main()
