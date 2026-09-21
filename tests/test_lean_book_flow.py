"""Two-chapter lean literary flow without strict task packages."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.lean_book_audit import audit_lean_book
from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.application.scene_transaction import SceneTransactionService
from literary_engineering_studio.automation.lean_scene_loop import LeanSceneRunCoordinator
from literary_engineering_studio.infrastructure.project_scene_transactions import (
    AtomicProjectSceneCommitter, ProjectSceneBriefProvider,
)
from literary_engineering_studio.persistence.scene_transactions import (
    SCENE_TRANSACTION_SCHEMA_SQL, SceneTransactionRepository,
)
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio.automation.lean_release import LeanWholeBookReleaseCoordinator
from literary_engineering_studio_engine.public.literary import (
    CreativeResult, ReviewDecision, ReviewResult, SceneDelta, SceneExecutionMode,
)

from tests.test_lean_longform_plan import _scene
from tests.test_lean_longform_planning_service import _Gateway


class _Writer:
    def create_scene(self, transaction_id, brief):
        del transaction_id
        return CreativeResult(
            prose="潮" * brief.length.target_hanzi,
            decision_summary="人物承担承诺的代价。",
            scene_delta=SceneDelta(next_handoff=("继续索偿",)),
        )

    def review_scene(self, transaction_id, brief, result, verification):
        return ReviewResult(ReviewDecision.PASS, "合格")

    def revise_scene(self, transaction_id, brief, result, verification, review, *, attempt):
        return result


class LeanBookFlowTests(unittest.TestCase):
    def test_two_chapters_reach_release_without_strict_route_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            (root / "project.yaml").write_text(
                "title: 渡口\ntarget_length: 2000\ntarget_chapters: 2\ntarget_scenes: 2\n",
                encoding="utf-8",
            )
            gateway = _Gateway([
                {
                    "premise": "旧信改变渡口的秩序",
                    "central_question": "林昭会否兑现旧约？",
                    "ending_choice": "他选择承担后果",
                    "volume_obligations": ["承诺逐步兑现"],
                    "chapters": [
                        {"title": "旧信", "dramatic_turn": "承诺公开", "obligation": "发现旧约", "reader_question": "信是谁写的？"},
                        {"title": "索偿", "dramatic_turn": "索偿到来", "obligation": "兑现旧约", "reader_question": "谁承担代价？"},
                    ],
                    "first_window": [_scene("读信")],
                },
                {"scenes": [_scene("索偿")]},
            ])
            data_root = Path(temporary) / "data"
            data_root.mkdir()
            planning = LeanLongformPlanningService({}, data_root=data_root, gateway=gateway)
            planning.ensure_initial(root)
            uow = SqliteUnitOfWork(data_root / "studio.sqlite3")
            with uow.write() as connection:
                connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
            repository = SceneTransactionRepository(uow)
            writer = _Writer()
            coordinator = LeanSceneRunCoordinator(
                project_root=root, data_root=data_root, planning=planning,
                service=SceneTransactionService(
                    briefs=ProjectSceneBriefProvider(), runtime=writer, critic=writer,
                    repository=repository, commits=AtomicProjectSceneCommitter(root),
                ),
                repository=repository, revision_runtime=writer,
            )
            actions = []
            for _ in range(30):
                step = coordinator.advance_one(mode=SceneExecutionMode.STANDARD, steward_approved=True)
                actions.append(step.action)
                if step.blocked:
                    self.fail(step.message)
                if step.route_ready:
                    break
            self.assertTrue(step.route_ready, actions)
            self.assertIn("planning-window", actions)
            self.assertEqual(len(gateway.calls), 2)
            self.assertEqual(audit_lean_book(root, data_root)["scene_count"], 2)
            result = LeanWholeBookReleaseCoordinator(
                {"application": {"data_root": str(data_root)}}
            ).release(root, approved_by="studio-user")
            self.assertTrue((root / result["manifest"]["outputs"]["docx"]["path"]).is_file())
            self.assertEqual(len(result["manifest"]["source_chapters"]), 2)
            self.assertFalse((root / "workflow" / "tasks").exists())
            self.assertFalse((root / "reviews").exists())


if __name__ == "__main__":
    unittest.main()
