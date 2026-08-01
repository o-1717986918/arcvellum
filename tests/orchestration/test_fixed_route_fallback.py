from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    DefaultPlanFactory,
    FreedomBudget,
    NormalizationContext,
    PlanLintContext,
    ChapterPlanningFacts,
    ScenePlanningFact,
    evaluate_chapter_plan_shadow,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    simulation_context_for_graph,
)


class FixedRouteFallbackTests(unittest.TestCase):
    def test_default_plan_is_the_fixed_formal_route_macro(self):
        factory = DefaultPlanFactory()
        plan = factory.create(
            base_project_fingerprint=FINGERPRINT,
            created_at="2026-07-26T00:00:00+00:00",
        )

        self.assertEqual(plan.route_macro_id, "fixed-formal-route.v1")
        self.assertEqual(plan.task_nodes, ())

    def test_shadow_evaluation_falls_back_without_activating_a_plan(self):
        budget = FreedomBudget(**freedom_budget())
        normalization = NormalizationContext(
            base_project_fingerprint=FINGERPRINT,
            approved_budget=budget,
            created_at="2026-07-26T00:00:00+00:00",
        )
        lint = PlanLintContext(
            current_project_fingerprint=FINGERPRINT,
            known_scope_refs=frozenset({"chapter_01", "scene_0001"}),
            allowed_capability_ids=frozenset({"project.query"}),
            authorized_budget=budget,
        )
        facts = ChapterPlanningFacts(
            chapter_id="chapter_01",
            scenes=(
                ScenePlanningFact(scene_ref="scene_0001"),
                ScenePlanningFact(scene_ref="scene_0001"),
            ),
            base_project_revision="rev-1",
        )

        evaluation = evaluate_chapter_plan_shadow(
            scene_plan_candidate(),
            facts=facts,
            active_scene_id="scene_0001",
            horizon_size=2,
            normalization_context=normalization,
            lint_context=lint,
            simulation_context_factory=simulation_context_for_graph,
        )

        self.assertFalse(evaluation.passed)
        self.assertIsNone(evaluation.plan_evaluation)
        self.assertIsNone(evaluation.policy)
        self.assertIn(
            "duplicate-scene-refs",
            {item.code for item in evaluation.violations},
        )


if __name__ == "__main__":
    unittest.main()
