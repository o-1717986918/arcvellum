from __future__ import annotations

import unittest

from literary_engineering_studio_engine.literary.scene.facts import SceneFacts
from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
    CreativeResult,
    IssueSeverity,
    LengthTarget,
    ReviewDecision,
    ReviewResult,
    RhythmDirective,
    SceneDelta,
    SceneExecutionMode,
    SceneRisk,
    SceneRiskLevel,
    StyleMountRef,
    build_scene_brief,
    build_scene_commit_plan,
    derive_scene_policy,
    scene_brief_issues,
    verify_creative_result,
)


def _facts() -> SceneFacts:
    return SceneFacts(
        scene_id="scene_0001",
        chapter_id="chapter_0001",
        location="旧车站",
        participants=["character/protagonist"],
        canon_refs=["canon/rain"],
        active_foreshadowing=[],
        scene_goal="主角决定登上末班车",
        external_conflict="车门即将关闭",
        internal_conflict="他不愿离开故乡",
        style_constraints=["克制"],
        next_hooks=["车厢里有人叫出他的旧名"],
        viewpoint="protagonist",
        incoming_pressure="上一场留下的车票即将失效",
        word_count_target=1200,
        word_count_min=900,
        word_count_max=1600,
    )


def _brief(*, risk: SceneRiskLevel = SceneRiskLevel.LOW):
    return build_scene_brief(
        _facts(),
        risk=SceneRisk(risk, ("relationship-state-change",)),
        scene_function="decision-turn",
        canon_constraints=("末班车在午夜前离站",),
        chapter_obligations=("推进离乡承诺",),
        rhythm=RhythmDirective(
            pace="slow-to-fast",
            detail="selective",
            scene_turn="犹豫转为行动",
            reader_effect="短暂松弛后产生疑问",
        ),
        style_mount=StyleMountRef("plain-flowing", "v1"),
        source_refs=("characters/protagonist.yaml",),
    )


def _result(prose: str = "雨停了。他收好车票，赶在车门合上前登车。") -> CreativeResult:
    return CreativeResult(
        prose=prose,
        decision_summary="让行动承担离乡决定，避免解释性独白。",
        scene_delta=SceneDelta(
            character_changes=(
                ChangeProposal(
                    target_ref="character/protagonist",
                    summary="从犹豫转为离开故乡",
                    evidence="赶在车门合上前登车",
                ),
            ),
            next_handoff=("陌生人叫出主角旧名",),
        ),
    )


class LeanKernelV2DomainTests(unittest.TestCase):
    def test_scene_brief_reuses_scene_facts_without_runtime_metadata(self) -> None:
        brief = _brief()

        self.assertEqual(brief.incoming_handoff, ("上一场留下的车票即将失效",))
        self.assertEqual(brief.length, LengthTarget(1200, 900, 1600))
        self.assertEqual(scene_brief_issues(brief), ())
        payload = brief.to_dict()
        self.assertEqual(payload["risk"]["level"], "low")
        self.assertNotIn("task_id", payload)
        self.assertNotIn("expected_outputs", payload)

    def test_risk_names_map_from_strict_v1_without_importing_studio(self) -> None:
        self.assertIs(SceneRiskLevel.from_compatible_value("compact"), SceneRiskLevel.LOW)
        self.assertIs(SceneRiskLevel.from_compatible_value("deep"), SceneRiskLevel.HIGH)
        self.assertIs(
            SceneRiskLevel.from_compatible_value("standard"),
            SceneRiskLevel.STANDARD,
        )

    def test_policy_defers_only_low_risk_scene_review(self) -> None:
        low = derive_scene_policy(
            mode=SceneExecutionMode.STANDARD,
            risk=SceneRisk(SceneRiskLevel.LOW),
        )
        standard = derive_scene_policy(
            mode=SceneExecutionMode.STANDARD,
            risk=SceneRisk(SceneRiskLevel.STANDARD),
        )
        high = derive_scene_policy(
            mode=SceneExecutionMode.STANDARD,
            risk=SceneRisk(SceneRiskLevel.HIGH),
        )

        self.assertTrue(low.defer_semantic_review_to_chapter)
        self.assertFalse(low.independent_review_required)
        self.assertTrue(standard.independent_review_required)
        self.assertTrue(high.explicit_decision_trace_required)
        self.assertTrue(high.steward_approval_required)

    def test_draft_mode_defers_standard_review_but_keeps_high_risk_protection(self) -> None:
        standard = derive_scene_policy(
            mode=SceneExecutionMode.DRAFT,
            risk=SceneRisk(SceneRiskLevel.STANDARD),
        )
        high = derive_scene_policy(
            mode=SceneExecutionMode.DRAFT,
            risk=SceneRisk(SceneRiskLevel.HIGH),
        )

        self.assertFalse(standard.independent_review_required)
        self.assertTrue(standard.defer_semantic_review_to_chapter)
        self.assertTrue(high.independent_review_required)
        self.assertTrue(high.steward_approval_required)

    def test_length_range_is_advisory_but_process_residue_is_hard(self) -> None:
        brief = _brief()
        policy = derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk)
        report = verify_creative_result(
            brief,
            _result("短句。\n\n## 工作流\ntask_complete"),
            policy,
            known_refs={"character/protagonist"},
        )

        self.assertIn("below-soft-length", {issue.code for issue in report.warnings})
        self.assertIn("process-trace-in-prose", {issue.code for issue in report.hard_failures})
        self.assertFalse(report.can_commit)

    def test_unknown_delta_reference_is_a_hard_failure(self) -> None:
        brief = _brief()
        result = CreativeResult(
            prose="雨停了。他登上车，车门随即合拢。",
            decision_summary="以动作完成场景转向。",
            scene_delta=SceneDelta(
                canon_candidates=(
                    ChangeProposal("canon/missing", "新增一条不存在的事实引用"),
                )
            ),
        )
        report = verify_creative_result(
            brief,
            result,
            derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk),
            known_refs={"character/protagonist"},
        )

        self.assertIn("unknown-delta-target", {issue.code for issue in report.hard_failures})

    def test_commit_plan_obeys_review_policy(self) -> None:
        brief = _brief(risk=SceneRiskLevel.STANDARD)
        policy = derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk)
        result = _result()
        report = verify_creative_result(
            brief,
            result,
            policy,
            known_refs={"character/protagonist"},
        )

        with self.assertRaisesRegex(ValueError, "independent review is required"):
            build_scene_commit_plan(
                transaction_id="tx-1",
                base_revision="rev-1",
                result=result,
                verification=report,
                policy=policy,
            )

        plan = build_scene_commit_plan(
            transaction_id="tx-1",
            base_revision="rev-1",
            result=result,
            verification=report,
            policy=policy,
            review=ReviewResult(ReviewDecision.PASS, "场景完成了有效变化。"),
        )
        self.assertEqual(plan.scene_id, "scene_0001")
        self.assertEqual(plan.review_decision, ReviewDecision.PASS)

    def test_verification_report_serializes_enum_values(self) -> None:
        brief = _brief()
        report = verify_creative_result(
            brief,
            _result(),
            derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk),
            known_refs={"character/protagonist"},
        )

        payload = report.to_dict()
        self.assertEqual(payload["issues"][0]["severity"], IssueSeverity.WARNING.value)
        self.assertTrue(payload["can_commit"])


if __name__ == "__main__":
    unittest.main()
