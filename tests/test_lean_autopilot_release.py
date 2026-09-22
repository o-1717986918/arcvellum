"""Lean Autopilot reaches release without the strict task runner."""

from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from literary_engineering_studio.application.lean_longform_planning import LeanLongformPlanningService
from literary_engineering_studio.application.scene_transaction import SceneTransactionService
from literary_engineering_studio.automation.controller import AutopilotService, ROUTE_ORDER
from literary_engineering_studio.automation.policy import DelegationPolicy, default_policy
from literary_engineering_studio.automation.run_loop import ClaimedRunLoop
from literary_engineering_studio.infrastructure.project_scene_transactions import (
    AtomicProjectSceneCommitter, ProjectSceneBriefProvider,
)
from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.automation.lean_scene_loop import LeanSceneRunCoordinator

from tests.test_lean_book_flow import _Writer
from tests.test_lean_longform_plan import _scene
from tests.test_lean_longform_planning_service import _Gateway


class LeanAutopilotReleaseTests(unittest.TestCase):
    def test_two_chapters_release_through_real_route_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "work"
            root.mkdir()
            (root / "project.yaml").write_text(
                "title: 渡口\ntarget_length: 2000\ntarget_chapters: 2\ntarget_scenes: 2\n",
                encoding="utf-8",
            )
            gateway = _Gateway([
                {
                    "premise": "一封旧信重新开启渡口的承诺",
                    "central_question": "林昭会否兑现旧约？",
                    "ending_choice": "他选择承担后果",
                    "volume_obligations": ["承诺逐步兑现"],
                    "chapters": [
                        {"title": "第一章 旧信", "dramatic_turn": "承诺公开", "obligation": "发现旧约", "reader_question": "信是谁写的？"},
                        {"title": "索偿", "dramatic_turn": "索偿到来", "obligation": "兑现旧约", "reader_question": "谁承担代价？"},
                    ],
                    "first_window": [_scene("读信")],
                    "characters": [{
                        "name": "林昭", "role": "必须兑现旧约的主角",
                        "importance": "major", "background": "渡口长大的摆渡人",
                        "desire": "守住渡口与承诺",
                    }],
                    "world_facts": ["渡口只在每月初一开船"],
                },
                {"scenes": [_scene("索偿")]},
            ])
            planning = LeanLongformPlanningService(
                {}, data_root=base, gateway=gateway,
            )
            store = JobStore(base / "studio.sqlite3")
            policy = default_policy("full_auto", literary_kernel="lean-v2")
            run = store.create_autopilot_run(
                str(root.resolve()), mode="full_auto", runtime="pi-worker", policy=policy,
            )
            config = {
                "application": {"data_root": str(base)},
                "agent_runtime_roles": {"worker": "pi-worker", "reviewer": "pi-worker"},
            }
            service = AutopilotService(config, store)
            writer = _Writer()
            coordinator = LeanSceneRunCoordinator(
                project_root=root, data_root=base, planning=planning,
                service=SceneTransactionService(
                    briefs=ProjectSceneBriefProvider(), runtime=writer, critic=writer,
                    repository=service.scene_transactions,
                    commits=AtomicProjectSceneCommitter(root),
                ),
                repository=service.scene_transactions, revision_runtime=writer,
            )
            service._lean_scene_coordinator = lambda _run_id, _project: coordinator
            service._worker = MagicMock(side_effect=AssertionError("strict worker called"))
            with patch(
                "literary_engineering_studio.automation.lean_route_host.LeanLongformPlanningService",
                return_value=planning,
            ), patch(
                "literary_engineering_studio.automation.lean_route_host.enrich_lean_planning_assets",
                return_value={"background_stories_created": 0, "world_rules_enriched": 0},
            ):
                ClaimedRunLoop(
                    service, run_id=run["run_id"], project=root,
                    policy=DelegationPolicy(policy), steward=MagicMock(),
                    stop=threading.Event(), route_order=ROUTE_ORDER,
                    dependency_probe=lambda _project: False,
                ).run()

            final = store.read_autopilot_run(run["run_id"])
            self.assertEqual(final["status"], "complete")
            self.assertEqual(len(gateway.calls), 2)
            self.assertFalse((root / "workflow" / "tasks").exists())
            self.assertFalse((root / "reviews").exists())
            self.assertTrue((root / "drafts" / "scenes" / "scene_0002.md").is_file())
            self.assertIn("摆渡人", (root / "characters" / "林昭.yaml").read_text(encoding="utf-8"))
            self.assertIn("每月初一", (root / "canon" / "world_rules.yaml").read_text(encoding="utf-8"))
            self.assertTrue(list((root / "releases").rglob("*.docx")))
            chapter = (root / "exports" / "chapter_0001" / "chapter_0001_novel.md").read_text(encoding="utf-8")
            self.assertIn("# 第1章 旧信", chapter)
            self.assertNotIn("第1章 第一章", chapter)
            actuals = (root / "workflow" / "book_actuals.json").read_text(encoding="utf-8")
            self.assertIn('"projection": "live-formal-scenes"', actuals)
            self.assertIn('"actual_chinese_content_chars":', actuals)
            checkpoints = [
                item for item in store.autopilot_events_since(run["run_id"], 0, limit=200)
                if item.get("event") == "lean_scene.chapter-checkpoint"
            ]
            self.assertEqual(len(checkpoints), 2)
            self.assertEqual(
                {item["data"]["chapter_id"] for item in checkpoints},
                {"chapter_0001", "chapter_0002"},
            )
            service._worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
