from __future__ import annotations

import unittest

from literary_engineering_studio.application.chapter_checkpoint import (
    ChapterCheckpointService,
    ChapterSceneOutcome,
    ProjectPlanBundle,
)
from literary_engineering_studio.orchestration.chapter_facts import (
    ChapterPlanningFacts,
    ScenePlanningFact,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
    SceneDelta,
)


def _bundle() -> ProjectPlanBundle:
    return ProjectPlanBundle(
        chapter=ChapterPlanningFacts(
            chapter_id="chapter_0001",
            scenes=(
                ScenePlanningFact("scene_0001", 300, "setup", "slow"),
                ScenePlanningFact("scene_0002", 300, "conflict", "fast"),
                ScenePlanningFact("scene_0003", 300, "aftermath", "restrained"),
            ),
            chapter_word_target=900,
            rhythm_contract_hash="rhythm-v1",
            promise_obligation_ids=("promise/letter",),
            obligation_contract_present=True,
            base_project_revision="revision-1",
        ),
        story_spine_ref="plot/story_architecture.json",
        word_budget_ref="plot/word_budget.json",
        scene_inventory_ref="plot/scene_inventory.json",
        obligation_ref="plot/chapter_obligations/chapter_0001.json",
    )


def _outcomes() -> tuple[ChapterSceneOutcome, ...]:
    return (
        ChapterSceneOutcome(
            "scene_0001",
            300,
            {
                "pace": "slow",
                "rhythm_role": "setup",
                "scene_function": "setup",
                "tension_curve": {"entry": 1, "peak": 2, "exit": 2},
            },
            (),
            SceneDelta(next_handoff=("主人公必须回答信件来源",)),
            0.82,
        ),
        ChapterSceneOutcome(
            "scene_0002",
            300,
            {
                "pace": "fast",
                "rhythm_role": "conflict",
                "scene_function": "conflict",
                "tension_curve": {"entry": 2, "peak": 4, "exit": 3},
            },
            ("接住信件来源的追问",),
            SceneDelta(
                continuity_changes=(
                    ChangeProposal(
                        "continuity/letter-holder",
                        "信被妹妹拿回",
                        "妹妹把信收进衣袋",
                    ),
                ),
                next_handoff=("母亲听见争执",),
            ),
            0.80,
        ),
        ChapterSceneOutcome(
            "scene_0003",
            300,
            {
                "pace": "restrained",
                "rhythm_role": "aftermath",
                "scene_function": "aftermath",
                "tension_curve": {"entry": 3, "peak": 3, "exit": 2},
            },
            ("接住母亲听见争执的压力",),
            SceneDelta(
                promise_updates=(
                    ChangeProposal(
                        "promise/letter",
                        "信件承诺在本章推进但暂未完全兑现",
                        "母亲要求天亮后说明来历",
                    ),
                )
            ),
            0.79,
        ),
    )


class LeanKernelV2ChapterCheckpointTests(unittest.TestCase):
    def test_three_scene_chapter_passes_one_aggregated_checkpoint(self) -> None:
        evaluation = ChapterCheckpointService().evaluate(_bundle(), _outcomes())

        self.assertEqual(evaluation.status, "pass")
        self.assertEqual(evaluation.scene_count, 3)
        self.assertEqual(evaluation.actual_hanzi, 900)
        self.assertEqual(evaluation.revision_plan, ())

    def test_missing_scene_and_severe_length_deficit_require_revision(self) -> None:
        evaluation = ChapterCheckpointService().evaluate(_bundle(), _outcomes()[:1])

        self.assertEqual(evaluation.status, "revision-required")
        self.assertFalse(evaluation.may_continue)
        codes = {item.code for item in evaluation.issues}
        self.assertIn("missing-committed-scenes", codes)
        self.assertIn("severe-chapter-length-deficit", codes)

    def test_soft_cross_scene_quality_findings_do_not_hard_block(self) -> None:
        outcomes = tuple(
            ChapterSceneOutcome(
                item.scene_id,
                item.body_hanzi,
                {
                    "pace": "fast",
                    "rhythm_role": "conflict",
                    "scene_function": "conflict",
                    "tension_curve": {"entry": 4, "peak": 5, "exit": 4},
                },
                () if item.scene_id != "scene_0001" else item.incoming_handoff,
                SceneDelta(
                    continuity_changes=(
                        ChangeProposal("continuity/letter-holder", "持有人改变"),
                    ),
                    next_handoff=("下一场压力",),
                ),
                0.4 if item.scene_id == "scene_0003" else 0.9,
            )
            for item in _outcomes()
        )

        evaluation = ChapterCheckpointService().evaluate(_bundle(), outcomes)

        self.assertEqual(evaluation.status, "needs-attention")
        self.assertTrue(evaluation.may_continue)
        codes = {item.code for item in evaluation.issues}
        self.assertIn("flat_pace_run", codes)
        self.assertIn("sustained_high_pressure", codes)
        self.assertIn("missing-scene-handoff", codes)
        self.assertIn("untouched-chapter-promises", codes)
        self.assertIn("continuity-change-without-evidence", codes)
        self.assertIn("chapter-style-drift", codes)


if __name__ == "__main__":
    unittest.main()
