from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    MAX_HORIZON_SIZE,
    MIN_HORIZON_SIZE,
    SceneRiskFacts,
    SceneRiskLevel,
    build_rolling_horizon,
    build_scene_risk_profile,
    effective_risk_level,
    machine_minimum_risk_level,
    rolling_horizon_violations,
    scene_risk_violations,
)


class RollingHorizonWindowTests(unittest.TestCase):
    def test_default_deep_window_follows_active_scene(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=[
                "scene_0001",
                "scene_0002",
                "scene_0003",
                "scene_0004",
                "scene_0005",
                "scene_0006",
                "scene_0007",
                "scene_0008",
            ],
            active_scene_id="scene_0002",
            horizon_size=3,
            base_project_revision="rev-1",
        )

        self.assertEqual(
            window.deep_scene_ids,
            ("scene_0003", "scene_0004", "scene_0005"),
        )
        self.assertEqual(window.horizon_size, 3)
        self.assertEqual(window.base_project_revision, "rev-1")

    def test_explicit_deep_window_is_preserved(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002", "scene_0003"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            deep_scene_ids=("scene_0003",),
        )

        self.assertEqual(window.deep_scene_ids, ("scene_0003",))

    def test_near_chapter_end_window_is_bounded(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002", "scene_0003"],
            active_scene_id="scene_0002",
            horizon_size=4,
            base_project_revision="rev-1",
        )

        self.assertEqual(window.deep_scene_ids, ("scene_0003",))

    def test_last_active_scene_has_empty_deep_window(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002"],
            active_scene_id="scene_0002",
            horizon_size=2,
            base_project_revision="rev-1",
        )

        self.assertEqual(window.deep_scene_ids, ())
        self.assertEqual(rolling_horizon_violations(window), ())

    def test_rebase_after_is_preserved(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            rebase_after=("canon", "character-state"),
        )

        self.assertEqual(window.rebase_after, ("canon", "character-state"))

    def test_active_outside_planned_raises(self):
        with self.assertRaises(ValueError):
            build_rolling_horizon(
                chapter_id="chapter_01",
                planned_scene_ids=["scene_0001"],
                active_scene_id="scene_0009",
                horizon_size=2,
                base_project_revision="rev-1",
            )

    def test_horizon_out_of_range_raises(self):
        for size in (MIN_HORIZON_SIZE - 1, MAX_HORIZON_SIZE + 1):
            with self.assertRaises(ValueError):
                build_rolling_horizon(
                    chapter_id="chapter_01",
                    planned_scene_ids=["scene_0001", "scene_0002"],
                    active_scene_id="scene_0001",
                    horizon_size=size,
                    base_project_revision="rev-1",
                )

    def test_empty_planned_raises(self):
        with self.assertRaises(ValueError):
            build_rolling_horizon(
                chapter_id="chapter_01",
                planned_scene_ids=[],
                active_scene_id="scene_0001",
                horizon_size=2,
                base_project_revision="rev-1",
            )

    def test_duplicate_planned_scenes_are_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0001", "scene_0002"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("duplicate-planned-scenes", codes)

    def test_deep_scene_not_in_planned_is_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            deep_scene_ids=("scene_0099",),
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("deep-scene-not-planned", codes)

    def test_deep_scene_not_future_is_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002", "scene_0003"],
            active_scene_id="scene_0002",
            horizon_size=2,
            base_project_revision="rev-1",
            deep_scene_ids=("scene_0001",),
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("deep-scene-not-future", codes)

    def test_deep_window_exceeding_horizon_is_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002", "scene_0003"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            deep_scene_ids=("scene_0002", "scene_0003", "scene_0001"),
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("deep-scenes-exceed-horizon", codes)

    def test_empty_deep_window_while_scenes_remain_is_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="rev-1",
            deep_scene_ids=(),
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("empty-deep-window", codes)

    def test_missing_base_revision_is_flagged(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002"],
            active_scene_id="scene_0001",
            horizon_size=2,
            base_project_revision="",
        )

        codes = {item.code for item in rolling_horizon_violations(window)}
        self.assertIn("missing-base-revision", codes)

    def test_valid_window_has_no_violations(self):
        window = build_rolling_horizon(
            chapter_id="chapter_01",
            planned_scene_ids=["scene_0001", "scene_0002", "scene_0003", "scene_0004"],
            active_scene_id="scene_0001",
            horizon_size=3,
            base_project_revision="rev-1",
            rebase_after=("canon",),
        )

        self.assertEqual(rolling_horizon_violations(window), ())


class SceneRiskProfileTests(unittest.TestCase):
    def test_zero_facts_are_compact(self):
        facts = SceneRiskFacts(scene_id="scene_0001")

        self.assertEqual(machine_minimum_risk_level(facts), SceneRiskLevel.COMPACT)
        self.assertEqual(build_scene_risk_profile(facts).level, SceneRiskLevel.COMPACT)

    def test_standard_trigger_raises_level(self):
        facts = SceneRiskFacts(scene_id="scene_0001", canon_change=1)

        self.assertEqual(machine_minimum_risk_level(facts), SceneRiskLevel.STANDARD)

    def test_deep_trigger_wins_over_standard(self):
        facts = SceneRiskFacts(
            scene_id="scene_0001",
            canon_change=2,
            character_state_change=1,
        )

        self.assertEqual(machine_minimum_risk_level(facts), SceneRiskLevel.DEEP)

    def test_branch_ambiguity_and_continuity_debt_trigger_deep(self):
        facts = SceneRiskFacts(
            scene_id="scene_0001",
            branch_ambiguity=3,
            continuity_debt=3,
        )

        self.assertEqual(machine_minimum_risk_level(facts), SceneRiskLevel.DEEP)
        self.assertEqual(
            machine_minimum_risk_level(
                SceneRiskFacts(scene_id="scene_0001", branch_ambiguity=2)
            ),
            SceneRiskLevel.STANDARD,
        )

    def test_proposed_level_can_raise_but_not_lower(self):
        compact = SceneRiskFacts(scene_id="scene_0001")
        raised = build_scene_risk_profile(
            compact,
            proposed_level=SceneRiskLevel.DEEP,
        )
        self.assertEqual(raised.level, SceneRiskLevel.DEEP)
        self.assertEqual(raised.minimum_level, SceneRiskLevel.COMPACT)
        self.assertIn("proposed-deep-above-minimum-compact", raised.reasons)

        standard = SceneRiskFacts(scene_id="scene_0001", canon_change=1)
        lowered = build_scene_risk_profile(
            standard,
            proposed_level=SceneRiskLevel.COMPACT,
        )
        self.assertEqual(lowered.level, SceneRiskLevel.STANDARD)
        self.assertEqual(lowered.minimum_level, SceneRiskLevel.STANDARD)

    def test_effective_risk_level_never_lowers(self):
        self.assertEqual(
            effective_risk_level(
                SceneRiskLevel.STANDARD,
                SceneRiskLevel.COMPACT,
            ),
            SceneRiskLevel.STANDARD,
        )
        self.assertEqual(
            effective_risk_level(
                SceneRiskLevel.COMPACT,
                SceneRiskLevel.DEEP,
            ),
            SceneRiskLevel.DEEP,
        )

    def test_reasons_include_triggered_features(self):
        profile = build_scene_risk_profile(
            SceneRiskFacts(scene_id="scene_0001", canon_change=2)
        )

        self.assertIn("canon_change>=deep:2", profile.reasons)
        self.assertNotIn("no-risk-feature-threshold", profile.reasons)

    def test_negative_feature_is_reported(self):
        facts = SceneRiskFacts(scene_id="scene_0001", canon_change=-1)

        codes = {item.code for item in scene_risk_violations(facts)}
        self.assertIn("invalid-risk-feature", codes)

    def test_missing_scene_id_is_reported(self):
        facts = SceneRiskFacts(scene_id="")

        codes = {item.code for item in scene_risk_violations(facts)}
        self.assertIn("missing-scene-id", codes)


if __name__ == "__main__":
    unittest.main()
