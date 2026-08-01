from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    ChapterPlanningFacts,
    ScenePlanningFact,
    SceneRiskLevel,
    evaluate_chapter_horizon_shadow,
    project_chapter_horizon,
)


def _facts(**overrides):
    base = dict(
        chapter_id="chapter_01",
        scenes=(
            ScenePlanningFact(scene_ref="scene_0001", function="hook"),
            ScenePlanningFact(
                scene_ref="scene_0002",
                word_target=1800,
                canon_change=2,
                climax_weight=4,
            ),
            ScenePlanningFact(
                scene_ref="scene_0003",
                word_target=1400,
                branch_ambiguity=2,
                continuity_debt=1,
            ),
            ScenePlanningFact(scene_ref="scene_0004", word_target=1600),
        ),
        chapter_word_target=9000,
        rhythm_contract_hash="rhythm-1",
        promise_obligation_ids=("promise_0001",),
        base_project_revision="rev-1",
    )
    base.update(overrides)
    return ChapterPlanningFacts(**base)


class ChapterHorizonProjectionTests(unittest.TestCase):
    def test_window_is_projected_from_fact_order(self):
        projection = project_chapter_horizon(
            _facts(),
            active_scene_id="scene_0001",
            horizon_size=3,
        )

        self.assertTrue(projection.passed)
        self.assertIsNotNone(projection.window)
        self.assertEqual(
            projection.window.deep_scene_ids,
            ("scene_0002", "scene_0003", "scene_0004"),
        )
        self.assertEqual(projection.window.horizon_size, 3)
        self.assertEqual(projection.window.base_project_revision, "rev-1")

    def test_risk_profiles_cover_every_planned_scene(self):
        projection = project_chapter_horizon(
            _facts(),
            active_scene_id="scene_0002",
            horizon_size=2,
        )

        self.assertEqual(
            [profile.scene_id for profile in projection.risk_profiles],
            ["scene_0001", "scene_0002", "scene_0003", "scene_0004"],
        )
        by_scene = {
            profile.scene_id: profile for profile in projection.risk_profiles
        }
        self.assertEqual(
            by_scene["scene_0001"].minimum_level,
            SceneRiskLevel.COMPACT,
        )
        self.assertEqual(
            by_scene["scene_0002"].minimum_level,
            SceneRiskLevel.DEEP,
        )
        self.assertEqual(
            by_scene["scene_0003"].minimum_level,
            SceneRiskLevel.STANDARD,
        )
        self.assertEqual(by_scene["scene_0002"].level, SceneRiskLevel.DEEP)

    def test_proposed_level_can_raise_a_compact_scene(self):
        projection = project_chapter_horizon(
            _facts(),
            active_scene_id="scene_0001",
            horizon_size=2,
            proposed_levels={"scene_0001": SceneRiskLevel.DEEP},
        )

        by_scene = {
            profile.scene_id: profile for profile in projection.risk_profiles
        }
        self.assertEqual(by_scene["scene_0001"].level, SceneRiskLevel.DEEP)
        self.assertEqual(
            by_scene["scene_0001"].minimum_level,
            SceneRiskLevel.COMPACT,
        )

    def test_duplicate_scene_refs_fail_closed(self):
        projection = project_chapter_horizon(
            _facts(
                scenes=(
                    ScenePlanningFact(scene_ref="scene_0001"),
                    ScenePlanningFact(scene_ref="scene_0001"),
                )
            ),
            active_scene_id="scene_0001",
            horizon_size=2,
        )

        self.assertFalse(projection.passed)
        self.assertIsNone(projection.window)
        self.assertEqual(projection.risk_profiles, ())
        codes = {item.code for item in projection.violations}
        self.assertIn("duplicate-scene-refs", codes)

    def test_negative_risk_feature_fails_closed(self):
        projection = project_chapter_horizon(
            _facts(
                scenes=(
                    ScenePlanningFact(scene_ref="scene_0001", canon_change=-1),
                )
            ),
            active_scene_id="scene_0001",
            horizon_size=2,
        )

        codes = {item.code for item in projection.violations}
        self.assertIn("invalid-risk-feature", codes)

    def test_active_scene_outside_inventory_is_invalid_window(self):
        projection = project_chapter_horizon(
            _facts(),
            active_scene_id="scene_0099",
            horizon_size=2,
        )

        self.assertFalse(projection.passed)
        self.assertIsNone(projection.window)
        codes = {item.code for item in projection.violations}
        self.assertIn("invalid-window", codes)

    def test_missing_base_revision_is_flagged(self):
        projection = project_chapter_horizon(
            _facts(base_project_revision=""),
            active_scene_id="scene_0001",
            horizon_size=2,
        )

        self.assertFalse(projection.passed)
        codes = {item.code for item in projection.violations}
        self.assertIn("missing-base-revision", codes)

    def test_shadow_evaluation_is_measure_only(self):
        evaluation = evaluate_chapter_horizon_shadow(
            _facts(),
            active_scene_id="scene_0001",
            horizon_size=2,
        )

        self.assertFalse(evaluation.executed)
        self.assertGreaterEqual(evaluation.timing_ms, 0.0)
        self.assertTrue(evaluation.projection.passed)

    def test_shadow_evaluation_matches_direct_projection(self):
        evaluation = evaluate_chapter_horizon_shadow(
            _facts(),
            active_scene_id="scene_0002",
            horizon_size=3,
        )
        direct = project_chapter_horizon(
            _facts(),
            active_scene_id="scene_0002",
            horizon_size=3,
        )

        self.assertEqual(
            evaluation.projection.window.deep_scene_ids,
            direct.window.deep_scene_ids,
        )
        self.assertEqual(
            evaluation.projection.risk_profiles,
            direct.risk_profiles,
        )


if __name__ == "__main__":
    unittest.main()
