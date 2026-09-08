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
)


def _project(root: Path) -> None:
    (root / "scenes").mkdir(parents=True)
    (root / "characters").mkdir()
    (root / "canon").mkdir()
    (root / "plot" / "chapter_obligations").mkdir(parents=True)
    (root / "plot" / "word_budget").mkdir()
    (root / "workflow" / "scene_deltas").mkdir(parents=True)
    (root / "workflow" / "scene_commits").mkdir()
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
    (root / "canon" / "world_rules.yaml").write_text("rules: [潮落前渡船停航]\n", encoding="utf-8")
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
            next_handoff=("渡船即将停航",),
        ),
        review_decision=ReviewDecision.PASS,
        steward_approved=False,
    )


class LeanProjectAdapterTests(unittest.TestCase):
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
            self.assertIn("characters/a-he.yaml", prepared.brief.source_refs)
            self.assertIn("阿禾", known_scene_refs(prepared.brief))
            self.assertTrue(prepared.base_revision)
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

    def test_changed_source_and_foreign_replay_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            provider = ProjectSceneBriefProvider()
            prepared = provider.prepare(root, "scene_0001", SceneExecutionMode.STANDARD)
            (root / "canon/world_rules.yaml").write_text("rules: [渡船已经停航]\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "source revision changed"):
                AtomicProjectSceneCommitter(root).commit(_plan(prepared))

            (root / "canon/world_rules.yaml").write_text("rules: [潮落前渡船停航]\n", encoding="utf-8")
            prepared = provider.prepare(root, "scene_0001", SceneExecutionMode.STANDARD)
            committer = AtomicProjectSceneCommitter(root)
            committer.commit(_plan(prepared))
            with self.assertRaisesRegex(RuntimeError, "another transaction"):
                committer.commit(_plan(prepared, transaction_id="tx-2"))


if __name__ == "__main__":
    unittest.main()
