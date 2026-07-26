from __future__ import annotations

from dataclasses import replace
import unittest

from literary_engineering_studio.orchestration import (
    FreedomBudget,
    NormalizationContext,
    PlanIssueSeverity,
    PlanLintContext,
    lint_plan,
    normalize_plan_candidate,
    parse_plan_candidate,
)
from literary_engineering_studio_engine.orchestration import GateId, PlanNodeKind

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate


class PlanNormalizerAndLintTests(unittest.TestCase):
    def setUp(self):
        self.approved = FreedomBudget(**freedom_budget())
        self.lint_context = PlanLintContext(
            current_project_fingerprint="project-revision-1",
            known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
            allowed_capability_ids=frozenset({"project.query"}),
            authorized_budget=self.approved,
        )

    def _plan(self, payload: dict | None = None, **context_changes):
        parsed = parse_plan_candidate(payload or scene_plan_candidate())
        context = NormalizationContext(
            base_project_fingerprint="project-revision-1",
            approved_budget=self.approved,
            created_at="2026-07-26T00:00:00+00:00",
            **context_changes,
        )
        return normalize_plan_candidate(parsed, context=context)

    def test_valid_scene_plan_is_normalized_and_passes_lint(self):
        plan = self._plan()
        result = lint_plan(plan, context=self.lint_context)

        self.assertTrue(result.passed, result.issues)
        self.assertEqual(result.status, "pass")
        self.assertEqual(len(plan.mandatory_gate_nodes), len(plan.task_nodes))
        prose_gates = next(
            item.gate_ids for item in plan.mandatory_gate_nodes if item.node_id == "prose"
        )
        self.assertIn(GateId.PROSE_SINGLE_WRITER.value, prose_gates)

    def test_normalizer_clamps_budget_branch_count_and_normalizes_ids(self):
        payload = scene_plan_candidate()
        payload["task_nodes"][0]["node_id"] = "Context Packet"
        payload["task_nodes"][1]["depends_on"] = ["Context Packet"]
        payload["strategy"]["branch_count"] = 20
        payload["freedom_request"]["max_branch_count"] = 20
        approved = replace(self.approved, max_branch_count=4)
        parsed = parse_plan_candidate(payload)

        plan = normalize_plan_candidate(
            parsed,
            context=NormalizationContext(
                base_project_fingerprint="project-revision-1",
                approved_budget=approved,
                created_at="2026-07-26T00:00:00+00:00",
            ),
        )

        self.assertEqual(plan.task_nodes[0].node_id, "context-packet")
        self.assertEqual(plan.task_nodes[1].depends_on, ("context-packet",))
        self.assertEqual(plan.freedom_budget.max_branch_count, 4)
        self.assertEqual(plan.strategy.branch_count, 4)
        self.assertTrue(any("clamped" in item for item in plan.candidate_warnings))

    def test_high_risk_normalization_injects_full_roleplay(self):
        plan = self._plan(risk_features_by_node={"roleplay": {"new_character": True}})
        gates = next(
            item.gate_ids for item in plan.mandatory_gate_nodes if item.node_id == "roleplay"
        )

        self.assertIn(GateId.FULL_ROLEPLAY.value, gates)

    def test_default_plan_identity_is_scoped_to_project_fingerprint(self):
        parsed = parse_plan_candidate(scene_plan_candidate())
        first = normalize_plan_candidate(
            parsed,
            context=NormalizationContext(
                base_project_fingerprint="project-revision-1",
                approved_budget=self.approved,
                created_at="2026-07-26T00:00:00+00:00",
            ),
        )
        second = normalize_plan_candidate(
            parsed,
            context=NormalizationContext(
                base_project_fingerprint="another-project-revision-1",
                approved_budget=self.approved,
                created_at="2026-07-26T00:00:00+00:00",
            ),
        )

        self.assertNotEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.candidate_digest, second.candidate_digest)

    def test_lint_rejects_cycle_stale_revision_and_unknown_capability(self):
        plan = self._plan()
        nodes = list(plan.task_nodes)
        nodes[0] = replace(nodes[0], depends_on=("state",), requested_capabilities=("shell.exec",))
        broken = replace(plan, task_nodes=tuple(nodes))
        stale_context = replace(self.lint_context, current_project_fingerprint="project-revision-2")

        result = lint_plan(broken, context=stale_context)
        codes = {issue.code for issue in result.issues if issue.severity == PlanIssueSeverity.ERROR}

        self.assertFalse(result.passed)
        self.assertTrue({"dag-cycle", "stale-project-revision", "capability"}.issubset(codes))

    def test_lint_rejects_missing_review_prose_budget_and_machine_gate(self):
        plan = self._plan()
        nodes = tuple(node for node in plan.task_nodes if node.kind != PlanNodeKind.SEMANTIC_REVIEW)
        prose_index = next(index for index, node in enumerate(nodes) if node.kind == PlanNodeKind.FORMAL_PROSE)
        prose = replace(nodes[prose_index], progress_contract=replace(nodes[prose_index].progress_contract, target_hanzi=0))
        nodes = (*nodes[:prose_index], prose, *nodes[prose_index + 1 :])
        bindings = tuple(item for item in plan.mandatory_gate_nodes if item.node_id != "prose")
        broken = replace(plan, task_nodes=nodes, mandatory_gate_nodes=bindings)

        result = lint_plan(broken, context=self.lint_context)
        codes = {issue.code for issue in result.issues if issue.severity == PlanIssueSeverity.ERROR}

        self.assertTrue({"prose-review", "prose-progress", "gate-binding"}.issubset(codes))

    def test_lint_rejects_two_formal_writers_for_one_scene(self):
        plan = self._plan()
        prose = next(node for node in plan.task_nodes if node.kind == PlanNodeKind.FORMAL_PROSE)
        duplicate = replace(prose, node_id="prose-copy", depends_on=("composition",))
        review = next(node for node in plan.task_nodes if node.kind == PlanNodeKind.SEMANTIC_REVIEW)
        nodes = tuple(
            replace(node, depends_on=("prose", "prose-copy"))
            if node.node_id == review.node_id
            else node
            for node in plan.task_nodes
        ) + (duplicate,)
        gates = plan.mandatory_gate_nodes + (
            replace(next(item for item in plan.mandatory_gate_nodes if item.node_id == "prose"), node_id="prose-copy"),
        )
        broken = replace(plan, task_nodes=nodes, mandatory_gate_nodes=gates)

        result = lint_plan(broken, context=self.lint_context)

        self.assertIn("multiple-prose-writers", {item.code for item in result.issues})

    def test_lint_rejects_invalid_budget_domains_from_python_callers(self):
        plan = replace(
            self._plan(),
            freedom_budget=replace(
                self.approved,
                max_parallel_read_tasks=0,
                max_research_cost=-1,
                max_analysis_to_production_ratio=1.5,
            ),
        )

        result = lint_plan(plan, context=self.lint_context)
        range_issues = [item for item in result.issues if item.code == "freedom-budget-range"]

        self.assertFalse(result.passed)
        self.assertEqual(len(range_issues), 3)

    def test_lint_rejects_parallel_prose_and_revision_for_one_scene(self):
        plan = self._plan()
        prose = next(node for node in plan.task_nodes if node.kind == PlanNodeKind.FORMAL_PROSE)
        review = next(node for node in plan.task_nodes if node.kind == PlanNodeKind.SEMANTIC_REVIEW)
        revision = replace(
            prose,
            node_id="revision",
            kind=PlanNodeKind.REVISION,
            depends_on=("composition",),
        )
        fresh_review = replace(
            review,
            node_id="revision-review",
            depends_on=("revision",),
        )
        nodes = (*plan.task_nodes, revision, fresh_review)
        prose_binding = next(
            item for item in plan.mandatory_gate_nodes if item.node_id == "prose"
        )
        review_binding = next(
            item for item in plan.mandatory_gate_nodes if item.node_id == "review"
        )
        bindings = (
            *plan.mandatory_gate_nodes,
            replace(prose_binding, node_id="revision"),
            replace(review_binding, node_id="revision-review"),
        )
        broken = replace(plan, task_nodes=nodes, mandatory_gate_nodes=bindings)

        result = lint_plan(broken, context=self.lint_context)

        self.assertFalse(result.passed)
        self.assertIn("parallel-creative-writers", {item.code for item in result.issues})

    def test_lint_rejects_scene_strategy_parameter_tampering(self):
        plan = self._plan()
        tampered_nodes = tuple(
            replace(
                node,
                parameters=tuple(
                    replace(parameter, value=5)
                    if parameter.name == "branch_count"
                    else parameter
                    for parameter in node.parameters
                ),
            )
            if node.kind == PlanNodeKind.BRANCH_SIMULATION
            else node
            for node in plan.task_nodes
        )

        result = lint_plan(
            replace(plan, task_nodes=tampered_nodes),
            context=self.lint_context,
        )

        self.assertFalse(result.passed)
        self.assertIn(
            "branch-strategy-binding",
            {item.code for item in result.issues},
        )

    def test_analysis_ratio_is_an_authorized_hard_limit(self):
        plan = self._plan()
        strict = replace(
            plan,
            freedom_budget=replace(
                plan.freedom_budget,
                max_analysis_to_production_ratio=0.1,
            ),
        )

        result = lint_plan(strict, context=self.lint_context)

        self.assertFalse(result.passed)
        self.assertIn("analysis-ratio", {item.code for item in result.issues})


if __name__ == "__main__":
    unittest.main()
