from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.orchestration import (
    ChapterFactsValidationMode,
    FreedomBudget,
    NormalizationContext,
    PlanLintContext,
    chapter_facts_violations,
    evaluate_chapter_plan_shadow_from_project,
    load_chapter_planning_facts,
)

from tests.orchestration.fixtures import freedom_budget, scene_plan_candidate
from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    simulation_context_for_graph,
)


def _scaffold_project(root: Path, *, with_plot: bool = True) -> None:
    (root / "scenes").mkdir(parents=True)
    (root / "scenes" / "scene_0001.yaml").write_text(
        "scene_id: scene_0001\n"
        "chapter_id: chapter_01\n"
        "title: 推进\n"
        "word_count_target: 1800\n"
        "time:\n"
        "  timeline_order: 2\n"
        "narrative_rhythm:\n"
        "  scene_function: [推进主线]\n"
        "  tension_curve: {entry: 2, peak: 5, exit: 4}\n"
        "new_asset_risk: 1\n",
        encoding="utf-8",
    )
    (root / "scenes" / "scene_0002.yaml").write_text(
        "scene_id: scene_0002\n"
        "chapter_id: chapter_01\n"
        "title: 开端\n"
        "word_count_target: 1400\n"
        "time:\n"
        "  timeline_order: 1\n"
        "narrative_rhythm:\n"
        "  scene_function: [建立前提]\n"
        "  tension_curve: {entry: 1, peak: 3, exit: 2}\n"
        "obligations: [promise_0001]\n",
        encoding="utf-8",
    )
    if not with_plot:
        return
    (root / "plot").mkdir()
    (root / "plot" / "rhythm_plan.json").write_text(
        json.dumps(
            {
                "revision": 1,
                "digest": "rhythm-digest-1",
                "entries": [
                    {
                        "scene_id": "scene_0001",
                        "pace": "slow_to_fast",
                        "scene_function": ["推进主线"],
                    },
                    {
                        "scene_id": "scene_0002",
                        "pace": "balanced",
                        "scene_function": ["建立前提"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "plot" / "word_budget").mkdir()
    (root / "plot" / "word_budget" / "word_budget.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "chapter_budgets": [
                    {
                        "chapter_id": "chapter_01",
                        "target_words": 9000,
                        "target_scene_count": 2,
                        "avg_scene_words": 1600,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "plot" / "chapter_obligations").mkdir()
    (root / "plot" / "chapter_obligations" / "chapter_01.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-workbench/chapter-obligation-contract/v1",
                "chapter_id": "chapter_01",
                "obligation_ids": ["promise_0001", "promise_0002"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class ChapterFactsIoAdapterTests(unittest.TestCase):
    def test_loader_orders_scenes_by_timeline_and_carries_budget_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _scaffold_project(root)

            facts = load_chapter_planning_facts(root, "chapter_01")

            self.assertEqual(
                [scene.scene_ref for scene in facts.scenes],
                ["scene_0002", "scene_0001"],
            )
            self.assertEqual(facts.scenes[0].word_target, 1400)
            self.assertEqual(facts.scenes[1].word_target, 1800)
            self.assertEqual(facts.chapter_word_target, 9000)
            self.assertEqual(facts.rhythm_contract_hash, "rhythm-digest-1")
            self.assertEqual(
                facts.promise_obligation_ids,
                ("promise_0001", "promise_0002"),
            )
            self.assertTrue(facts.obligation_contract_present)
            self.assertTrue(facts.base_project_revision)
            self.assertEqual(chapter_facts_violations(facts), ())
            self.assertEqual(
                chapter_facts_violations(
                    facts,
                    mode=ChapterFactsValidationMode.PRODUCTION,
                ),
                (),
            )

    def test_risk_signals_come_from_yaml_and_tension_curve(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _scaffold_project(root)

            facts = load_chapter_planning_facts(root, "chapter_01")
            by_scene = {scene.scene_ref: scene for scene in facts.scenes}

            self.assertEqual(by_scene["scene_0001"].climax_weight, 4)
            self.assertEqual(by_scene["scene_0001"].new_asset_risk, 1)
            self.assertEqual(by_scene["scene_0002"].climax_weight, 0)
            self.assertEqual(by_scene["scene_0001"].pace, "slow_to_fast")
            self.assertEqual(by_scene["scene_0001"].function, "推进主线")
            self.assertEqual(by_scene["scene_0002"].obligations, ("promise_0001",))

    def test_missing_optional_files_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _scaffold_project(root, with_plot=False)

            facts = load_chapter_planning_facts(root, "chapter_01")

            self.assertEqual(facts.chapter_word_target, 0)
            self.assertEqual(facts.rhythm_contract_hash, "")
            self.assertEqual(facts.promise_obligation_ids, ())
            self.assertFalse(facts.obligation_contract_present)
            self.assertEqual(facts.scenes[0].pace, "")
            self.assertEqual(chapter_facts_violations(facts), ())

            strict_codes = {
                item.code
                for item in chapter_facts_violations(
                    facts,
                    mode=ChapterFactsValidationMode.PRODUCTION,
                )
            }
            self.assertEqual(
                strict_codes,
                {
                    "missing-chapter-word-target",
                    "missing-rhythm-contract",
                    "missing-obligation-contract",
                    "missing-scene-pace",
                },
            )

    def test_missing_chapter_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _scaffold_project(root)

            with self.assertRaises(FileNotFoundError):
                load_chapter_planning_facts(root, "chapter_0099")

    def test_invalid_scene_yaml_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: [unclosed\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_chapter_planning_facts(root, "chapter_01")

    def test_contract_obligation_dicts_are_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _scaffold_project(root, with_plot=False)
            (root / "plot" / "chapter_obligations").mkdir(parents=True)
            (root / "plot" / "chapter_obligations" / "chapter_01.json").write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-workbench/chapter-obligation-contract/v1",
                        "chapter_id": "chapter_01",
                        "contract": {
                            "obligations": [
                                {"id": "promise_0001"},
                                {"obligation_id": "promise_0003"},
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            facts = load_chapter_planning_facts(root, "chapter_01")

            self.assertEqual(
                facts.promise_obligation_ids,
                ("promise_0001", "promise_0003"),
            )


class ChapterFactsIoShadowIntegrationTests(unittest.TestCase):
    def test_project_wrapper_runs_shadow_pipeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scenes").mkdir()
            (root / "scenes" / "scene_0001.yaml").write_text(
                "scene_id: scene_0001\n"
                "chapter_id: chapter_01\n"
                "word_count_target: 1800\n"
                "canon_change: 2\n",
                encoding="utf-8",
            )
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

            evaluation = evaluate_chapter_plan_shadow_from_project(
                root,
                "chapter_01",
                scene_plan_candidate(),
                active_scene_id="scene_0001",
                horizon_size=2,
                base_project_revision="rev-1",
                normalization_context=normalization,
                lint_context=lint,
                simulation_context_factory=simulation_context_for_graph,
            )

            self.assertTrue(evaluation.passed)
            self.assertFalse(evaluation.executed)
            self.assertEqual(
                evaluation.policy.scene_risk_levels,
                (("scene_0001", "deep"),),
            )


if __name__ == "__main__":
    unittest.main()
