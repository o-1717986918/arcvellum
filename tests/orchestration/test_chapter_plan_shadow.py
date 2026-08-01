from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    FreedomBudget,
    NormalizationContext,
    PlanLintContext,
    ChapterPlanningFacts,
    SceneRiskFacts,
    ScenePlanningFact,
    SceneRiskLevel,
    chapter_window_policy,
    evaluate_chapter_plan_shadow,
    project_chapter_candidate_parameters,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    simulation_context_for_graph,
)


def _facts(**overrides):
    base = dict(
        chapter_id="chapter_01",
        scenes=(
            ScenePlanningFact(
                scene_ref="scene_0001",
                canon_change=2,
                climax_weight=4,
            ),
            ScenePlanningFact(scene_ref="scene_0002"),
        ),
        chapter_word_target=6000,
        base_project_revision="rev-1",
    )
    base.update(overrides)
    return ChapterPlanningFacts(**base)


def _two_scene_candidate() -> dict:
    payload = scene_plan_candidate()
    payload["scope"]["scene_ids"] = ["scene_0001", "scene_0002"]
    payload["strategy"]["scene_inventory"].append(
        {
            "scene_ref": "scene_0002",
            "function": "turn",
            "pace": "medium",
            "roleplay_depth": "targeted",
        }
    )
    payload["task_nodes"] = [
        {
            "node_id": "roleplay-0001",
            "kind": "roleplay_simulation",
            "scope_refs": ["scene_0001"],
            "depends_on": [],
        },
        {
            "node_id": "branches-0001",
            "kind": "scene_branch_simulation",
            "scope_refs": ["scene_0001"],
            "depends_on": ["roleplay-0001"],
        },
        {
            "node_id": "roleplay-0002",
            "kind": "roleplay_simulation",
            "scope_refs": ["scene_0002"],
            "depends_on": [],
        },
        {
            "node_id": "branches-0002",
            "kind": "scene_branch_simulation",
            "scope_refs": ["scene_0002"],
            "depends_on": ["roleplay-0002"],
        },
    ]
    return payload


def _shadow_contexts():
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
    return normalization, lint


class ChapterWindowPolicyProjectionTests(unittest.TestCase):
    def test_candidate_parameters_follow_risk_profiles(self):
        projection = project_chapter_candidate_parameters(
            _two_scene_candidate(),
            window=None,  # type: ignore[arg-type]
            profiles=(
                _profile("scene_0001", SceneRiskLevel.DEEP),
                _profile("scene_0002", SceneRiskLevel.COMPACT),
            ),
        )
        payload, warnings = projection

        self.assertEqual(warnings, ())
        strategy = payload["strategy"]
        by_scene = {
            item["scene_ref"]: item["roleplay_depth"]
            for item in strategy["scene_inventory"]
        }
        self.assertEqual(by_scene["scene_0001"], "full")
        self.assertEqual(by_scene["scene_0002"], "light")
        self.assertEqual(strategy["branch_count"], 5)
        parameters = {
            node["node_id"]: dict(node.get("parameters") or {})
            for node in payload["task_nodes"]
        }
        self.assertEqual(parameters["roleplay-0001"]["roleplay_depth"], "full")
        self.assertEqual(parameters["roleplay-0002"]["roleplay_depth"], "light")
        self.assertEqual(parameters["branches-0001"]["branch_count"], 5)
        self.assertEqual(parameters["branches-0002"]["branch_count"], 5)

    def test_window_policy_carries_horizon_identity(self):
        window = _window()
        policy = chapter_window_policy(
            window,
            (
                _profile("scene_0001", SceneRiskLevel.DEEP),
                _profile("scene_0002", SceneRiskLevel.COMPACT),
            ),
        )

        self.assertEqual(policy.chapter_id, "chapter_01")
        self.assertEqual(policy.active_scene_id, "scene_0001")
        self.assertEqual(policy.deep_scene_ids, ("scene_0002",))
        self.assertEqual(policy.branch_count, 5)
        self.assertEqual(policy.scene_risk_levels[0], ("scene_0001", "deep"))


class ChapterPlanShadowEvaluationTests(unittest.TestCase):
    def test_shadow_evaluation_runs_existing_pipeline_with_projected_depth(self):
        normalization, lint = _shadow_contexts()
        evaluation = evaluate_chapter_plan_shadow(
            scene_plan_candidate(),
            facts=_facts(
                scenes=(ScenePlanningFact(scene_ref="scene_0001", canon_change=2),)
            ),
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            normalization_context=normalization,
            lint_context=lint,
            simulation_context_factory=simulation_context_for_graph,
        )

        self.assertTrue(evaluation.passed)
        self.assertFalse(evaluation.executed)
        self.assertIsNotNone(evaluation.policy)
        self.assertEqual(
            evaluation.policy.scene_risk_levels,
            (("scene_0001", "deep"),),
        )
        parameters = {
            node.node_id: {item.name: item.value for item in node.parameters}
            for node in evaluation.plan_evaluation.graph.nodes
        }
        self.assertEqual(parameters["roleplay"]["roleplay_depth"], "full")

    def test_invalid_facts_fail_before_pipeline(self):
        normalization, lint = _shadow_contexts()
        evaluation = evaluate_chapter_plan_shadow(
            scene_plan_candidate(),
            facts=_facts(
                scenes=(
                    ScenePlanningFact(scene_ref="scene_0001"),
                    ScenePlanningFact(scene_ref="scene_0001"),
                )
            ),
            active_scene_id="scene_0001",
            horizon_size=2,
            normalization_context=normalization,
            lint_context=lint,
            simulation_context_factory=simulation_context_for_graph,
        )

        self.assertFalse(evaluation.passed)
        self.assertIsNone(evaluation.policy)
        self.assertIsNone(evaluation.plan_evaluation)
        codes = {item.code for item in evaluation.violations}
        self.assertIn("duplicate-scene-refs", codes)


def _window():
    from literary_engineering_studio.orchestration import build_rolling_horizon

    return build_rolling_horizon(
        chapter_id="chapter_01",
        planned_scene_ids=["scene_0001", "scene_0002"],
        active_scene_id="scene_0001",
        horizon_size=2,
        base_project_revision="rev-1",
    )


def _profile(scene_id: str, level: SceneRiskLevel):
    from literary_engineering_studio.orchestration import build_scene_risk_profile

    return build_scene_risk_profile(
        SceneRiskFacts(
            scene_id=scene_id,
            canon_change=2 if level is SceneRiskLevel.DEEP else 0,
        ),
        proposed_level=level,
    )


if __name__ == "__main__":
    unittest.main()
