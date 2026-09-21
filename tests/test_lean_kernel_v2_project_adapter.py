from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.infrastructure.project_scene_transactions import (
    AtomicProjectSceneCommitter,
    ProjectSceneBriefProvider,
    known_scene_refs,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
    ReviewDecision,
    SceneCommitPlan,
    SceneDelta,
    SceneExecutionMode,
    project_committed_scene_delta,
)


def _project(root: Path) -> None:
    (root / "scenes").mkdir(parents=True)
    (root / "characters").mkdir()
    (root / "canon").mkdir()
    (root / "plot" / "chapter_obligations").mkdir(parents=True)
    (root / "plot" / "word_budget").mkdir()
    (root / "workflow" / "scene_deltas").mkdir(parents=True)
    (root / "workflow" / "scene_commits").mkdir()
    (root / "workflow" / "studio").mkdir()
    (root / "scenes" / "scene_0001.yaml").write_text(
        "scene_id: scene_0001\nchapter_id: chapter_01\nscene_goal: 守住约定\n"
        "participants: [阿禾]\nlocation: 渡口\nviewpoint: 阿禾\n"
        "input_state:\n  canon_refs: [canon/world_rules.yaml]\n"
        "narrative_rhythm:\n  scene_function: [建立承诺]\n"
        "  scene_turn: 等待转为行动\n  reader_effect: 感到时间逼近\n"
        "word_count_target: 900\nword_count_min: 700\nword_count_max: 1200\n"
        "character_state_change: 1\n",
        encoding="utf-8",
    )
    (root / "characters" / "a-he.yaml").write_text(
        "character_id: a-he\nname: 阿禾\nbelief: 约定必须兑现\n",
        encoding="utf-8",
    )
    (root / "canon" / "world_rules.yaml").write_text(
        "rules: [潮落前渡船停航]\nconstraints: [不得改写潮汐时刻]\n",
        encoding="utf-8",
    )
    (root / "canon" / "forbidden_changes.yaml").write_text(
        "forbidden_changes: [不得新增有专名的船员]\n", encoding="utf-8"
    )
    (root / "workflow" / "studio" / "user_directions.md").write_text(
        "# 当前用户创作方向\n\n只使用阿禾这一名正式人物。\n", encoding="utf-8"
    )
    (root / "plot" / "rhythm_plan.json").write_text(
        json.dumps({"entries": [{"scene_id": "scene_0001", "pace": "slow_to_fast"}]}),
        encoding="utf-8",
    )
    (root / "plot" / "word_budget" / "word_budget.json").write_text("{}", encoding="utf-8")
    (root / "plot" / "chapter_obligations" / "chapter_01.json").write_text(
        json.dumps({"obligation_ids": ["promise/ferry"]}), encoding="utf-8"
    )


def _plan(prepared, transaction_id="tx-1") -> SceneCommitPlan:
    return SceneCommitPlan(
        transaction_id=transaction_id,
        scene_id="scene_0001",
        base_revision=prepared.base_revision,
        prose="潮水退到第三块石阶时，阿禾终于站了起来。",
        scene_delta=SceneDelta(
            character_changes=(
                ChangeProposal("阿禾", "等待转为行动", "站了起来"),
            ),
            canon_candidates=(
                ChangeProposal("canon/ferry", "渡船即将停航", "潮水已退"),
            ),
            new_asset_candidates=(
                ChangeProposal("船老大", "渡口出现一名可能持续出场的船老大", "有人从船上应声", operation="create"),
            ),
            next_handoff=("渡船即将停航",),
        ),
        review_decision=ReviewDecision.PASS,
        steward_approved=False,
    )


class LeanProjectAdapterTests(unittest.TestCase):
    def test_reused_identity_ref_with_different_roles_is_visible_as_a_conflict(self):
        first = SceneDelta(new_asset_candidates=(
            ChangeProposal("老周", "复核组同事", "电话中确认流程", operation="create"),
        ))
        projection, _, _ = project_committed_scene_delta(
            scene_id="scene_0001", transaction_id="tx-1", delta=first,
        )
        second = SceneDelta(new_asset_candidates=(
            ChangeProposal("老周", "旧堤事故失踪工人", "名单中出现称谓", operation="create"),
        ))
        projection, _, _ = project_committed_scene_delta(
            scene_id="scene_0002", transaction_id="tx-2", delta=second,
            current_projection=projection,
        )

        self.assertEqual(projection["identity_conflicts"][0]["target_ref"], "老周")
        self.assertEqual(projection["identity_conflicts"][0]["scene_ids"], ["scene_0001", "scene_0002"])

    def test_project_facts_become_one_bounded_brief(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)

            prepared = ProjectSceneBriefProvider().prepare(
                root, "scene_0001", SceneExecutionMode.STANDARD
            )

            self.assertEqual(prepared.brief.scene_function, "建立承诺")
            self.assertEqual(prepared.brief.rhythm.pace, "slow_to_fast")
            self.assertEqual(prepared.brief.chapter_obligations, ("promise/ferry",))
            self.assertEqual(prepared.brief.risk.level.value, "standard")
            self.assertEqual(
                prepared.brief.canon_constraints,
                ("潮落前渡船停航", "不得改写潮汐时刻", "不得新增有专名的船员"),
            )
            self.assertIn("characters/a-he.yaml", prepared.brief.source_refs)
            self.assertIn("workflow/studio/user_directions.md", prepared.brief.source_refs)
            self.assertIn("阿禾", known_scene_refs(prepared.brief))
            self.assertNotIn("潮落前渡船停航", known_scene_refs(prepared.brief))
            self.assertTrue(prepared.base_revision)
            self.assertTrue(all(not Path(ref).is_absolute() for ref in prepared.brief.source_refs))

    def test_next_scene_reads_previous_formal_prose_as_source_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            (root / "drafts" / "scenes").mkdir(parents=True)
            (root / "drafts" / "scenes" / "scene_0001.md").write_text(
                "雨历十一日，阿禾在渡口等到潮退。\n", encoding="utf-8"
            )
            (root / "scenes" / "scene_0002.yaml").write_text(
                "scene_id: scene_0002\nchapter_id: chapter_01\nscene_goal: 追查失约原因\n"
                "participants: [阿禾]\nlocation: 渡口\nviewpoint: 阿禾\n"
                "word_count_target: 900\nword_count_min: 700\nword_count_max: 1200\n",
                encoding="utf-8",
            )

            prepared = ProjectSceneBriefProvider().prepare(
                root, "scene_0002", SceneExecutionMode.STANDARD
            )

            self.assertIn("drafts/scenes/scene_0001.md", prepared.brief.source_refs)
            self.assertEqual(prepared.brief.source_refs[1], "drafts/scenes/scene_0001.md")
            self.assertTrue(all(not Path(ref).is_absolute() for ref in prepared.brief.source_refs))

    def test_commit_is_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            prepared = ProjectSceneBriefProvider().prepare(
                root, "scene_0001", SceneExecutionMode.STANDARD
            )
            committer = AtomicProjectSceneCommitter(root)
            plan = _plan(prepared)

            first = committer.commit(plan)
            second = committer.commit(plan)

            self.assertEqual(first, second)
            self.assertTrue((root / "drafts/scenes/scene_0001.md").is_file())
            delta = json.loads((root / "workflow/scene_deltas/scene_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(delta["next_handoff"], ["渡船即将停航"])
            continuity = json.loads((root / "workflow/continuity/current.json").read_text(encoding="utf-8"))
            self.assertEqual(continuity["scene_count"], 1)
            self.assertEqual(continuity["open_identity_candidates"][0]["target_ref"], "船老大")
            facts = json.loads((root / "canon/facts.json").read_text(encoding="utf-8"))
            self.assertEqual(facts["candidates"][0]["statement"], "渡船即将停航")
            self.assertIn("scene_0001", (root / "canon/timeline.yaml").read_text(encoding="utf-8"))

    def test_structured_output_facts_raise_the_machine_minimum_risk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            scene = root / "scenes" / "scene_0001.yaml"
            text = scene.read_text(encoding="utf-8").replace(
                "character_state_change: 1\n",
                "output_state:\n  new_facts: [渡船事故由人为破坏造成]\n",
            )
            scene.write_text(text, encoding="utf-8")

            prepared = ProjectSceneBriefProvider().prepare(
                root, "scene_0001", SceneExecutionMode.STANDARD
            )

            self.assertEqual(prepared.brief.risk.level.value, "standard")
            self.assertIn("canon_change>=standard:1", prepared.brief.risk.reasons)

    def test_changed_source_and_foreign_replay_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            provider = ProjectSceneBriefProvider()
            prepared = provider.prepare(root, "scene_0001", SceneExecutionMode.STANDARD)
            (root / "canon/world_rules.yaml").write_text("rules: [渡船已经停航]\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "source revision changed"):
                AtomicProjectSceneCommitter(root).commit(_plan(prepared))

            (root / "canon/world_rules.yaml").write_text(
                "rules: [潮落前渡船停航]\nconstraints: [不得改写潮汐时刻]\n",
                encoding="utf-8",
            )
            prepared = provider.prepare(root, "scene_0001", SceneExecutionMode.STANDARD)
            committer = AtomicProjectSceneCommitter(root)
            committer.commit(_plan(prepared))
            with self.assertRaisesRegex(RuntimeError, "another transaction"):
                committer.commit(_plan(prepared, transaction_id="tx-2"))


if __name__ == "__main__":
    unittest.main()
