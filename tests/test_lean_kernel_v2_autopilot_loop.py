from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock

from literary_engineering_studio.application.scene_transaction import SceneTransactionService
from literary_engineering_studio.automation.lean_scene_loop import LeanSceneRunCoordinator
from literary_engineering_studio.automation.lean_scene_loop import LeanSceneStep
from literary_engineering_studio.automation.policy import DelegationPolicy, default_policy, normalize_policy
from literary_engineering_studio.automation.run_loop import ClaimedRunLoop
from literary_engineering_studio.automation.run_result_contracts import RouteCycle
from literary_engineering_studio.automation.controller import AutopilotService
from literary_engineering_studio.infrastructure.project_scene_transactions import (
    AtomicProjectSceneCommitter,
    ProjectSceneBriefProvider,
)
from literary_engineering_studio.persistence.scene_transactions import (
    SCENE_TRANSACTION_SCHEMA_SQL,
    SceneTransactionRepository,
)
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
    CreativeResult,
    ReviewDecision,
    ReviewResult,
    SceneDelta,
    SceneExecutionMode,
)


class _Runtime:
    def __init__(self, *, review_first: str = "pass"):
        self.creates = 0
        self.reviews = 0
        self.revisions = 0
        self.review_first = review_first

    def create_scene(self, transaction_id, brief):
        self.creates += 1
        return self._result("潮" * 320)

    def review_scene(self, transaction_id, brief, result, verification):
        self.reviews += 1
        decision = self.review_first if self.reviews == 1 else "pass"
        return ReviewResult(
            ReviewDecision(decision),
            "关系变化需要更具体" if decision == "revise" else "通过",
            ("把人物选择落实为可见行动",) if decision == "revise" else (),
        )

    def revise_scene(self, transaction_id, brief, result, verification, review, *, attempt):
        self.revisions += 1
        return self._result("潮" * 310 + "她终于兑现了承诺。")

    @staticmethod
    def _result(prose):
        return CreativeResult(
            prose=prose,
            decision_summary="以行动兑现本章承诺。",
            scene_delta=SceneDelta(
                promise_updates=(
                    ChangeProposal("promise/ferry", "承诺得到推进", "她开始行动"),
                ),
                next_handoff=("渡船即将离岸",),
            ),
        )


class _AlwaysReviseRuntime(_Runtime):
    def review_scene(self, transaction_id, brief, result, verification):
        self.reviews += 1
        return ReviewResult(
            ReviewDecision.REVISE,
            "仍需修订",
            ("再次修改",),
        )


def _project(root: Path, *, standard_risk: bool = False) -> None:
    for relative in (
        "scenes",
        "characters",
        "canon",
        "plot/word_budget",
        "plot/chapter_obligations",
        "plot/candidates/scenes",
        "workflow/scene_deltas",
        "workflow/scene_commits",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    risk = "character_state_change: 1\n" if standard_risk else ""
    (root / "scenes/scene_0001.yaml").write_text(
        "scene_id: scene_0001\nchapter_id: chapter_01\nscene_goal: 兑现渡口约定\n"
        "participants: [阿禾]\nword_count_target: 300\nword_count_min: 240\nword_count_max: 380\n"
        "time:\n  timeline_order: 1\n"
        "narrative_rhythm:\n  scene_function: [兑现承诺]\n"
        "  rhythm_role: payoff\n  scene_turn: 等待转为行动\n"
        "  reader_effect: 压力得到释放\n"
        "  tension_curve: {entry: 2, peak: 3, exit: 2}\n"
        + risk,
        encoding="utf-8",
    )
    (root / "characters/a-he.yaml").write_text("character_id: a-he\nname: 阿禾\n", encoding="utf-8")
    (root / "plot/rhythm_plan.json").write_text(
        json.dumps(
            {
                "digest": "rhythm-v1",
                "entries": [
                    {
                        "scene_id": "scene_0001",
                        "pace": "slow_to_fast",
                        "scene_function": ["兑现承诺"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "plot/word_budget/word_budget.json").write_text(
        json.dumps(
            {
                "chapter_budgets": [
                    {
                        "chapter_id": "chapter_01",
                        "target_words": 300,
                        "avg_scene_words": 300,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "plot/chapter_obligations/chapter_01.json").write_text(
        json.dumps({"obligation_ids": ["promise/ferry"]}), encoding="utf-8"
    )


def _coordinator(root: Path, runtime: _Runtime):
    uow = SqliteUnitOfWork(root / "studio.sqlite3")
    with uow.write() as connection:
        connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
    repository = SceneTransactionRepository(uow)
    service = SceneTransactionService(
        briefs=ProjectSceneBriefProvider(),
        runtime=runtime,
        critic=runtime,
        repository=repository,
        commits=AtomicProjectSceneCommitter(root),
        id_factory=lambda: "scene-tx-1",
    )
    return LeanSceneRunCoordinator(
        project_root=root,
        data_root=root / ".studio",
        service=service,
        repository=repository,
        revision_runtime=runtime,
    )


class LeanAutopilotLoopTests(unittest.TestCase):
    def test_policy_defaults_to_strict_and_accepts_explicit_lean_mode(self):
        self.assertEqual(default_policy()["literary_kernel"], "strict-v1")
        policy = normalize_policy(
            {
                "mode": "full_auto",
                "literary_kernel": "lean-v2",
                "scene_execution_mode": "draft",
            }
        )
        self.assertEqual(DelegationPolicy(policy).literary_kernel, "lean-v2")
        self.assertEqual(DelegationPolicy(policy).scene_execution_mode, "draft")

    def test_low_risk_scene_reaches_commit_and_chapter_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root)
            runtime = _Runtime()
            coordinator = _coordinator(root, runtime)

            actions = []
            for _ in range(8):
                step = coordinator.advance_one(
                    mode=SceneExecutionMode.STANDARD,
                    steward_approved=False,
                )
                actions.append(step.action)
                if step.route_ready:
                    break

            self.assertEqual(
                actions,
                ["prepared", "created", "verified", "committed", "chapter-checkpoint", "route-ready"],
            )
            self.assertEqual(runtime.creates, 1)
            self.assertEqual(runtime.reviews, 0)
            self.assertTrue((root / "drafts/scenes/scene_0001.md").is_file())
            self.assertEqual(
                len(list((root / ".studio").rglob("chapter_01.json"))),
                1,
            )

    def test_standard_review_can_request_one_revision_then_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root, standard_risk=True)
            runtime = _Runtime(review_first="revise")
            coordinator = _coordinator(root, runtime)

            actions = []
            for _ in range(12):
                step = coordinator.advance_one(
                    mode=SceneExecutionMode.STANDARD,
                    steward_approved=False,
                )
                actions.append(step.action)
                if step.committed:
                    break

            self.assertIn("revised", actions)
            self.assertEqual(runtime.creates, 1)
            self.assertEqual(runtime.revisions, 1)
            self.assertEqual(runtime.reviews, 2)
            self.assertEqual(actions[-1], "committed")

    def test_revision_budget_stops_before_a_second_model_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _project(root, standard_risk=True)
            runtime = _AlwaysReviseRuntime()
            coordinator = _coordinator(root, runtime)

            final = None
            for _ in range(12):
                final = coordinator.advance_one(
                    mode=SceneExecutionMode.STANDARD,
                    steward_approved=False,
                )
                if final.blocked:
                    break

            self.assertIsNotNone(final)
            self.assertTrue(final.blocked)
            self.assertIn("budget is exhausted", final.message)
            self.assertEqual(runtime.revisions, 1)

    def test_claimed_loop_dispatches_only_explicit_lean_scene_route(self):
        host = MagicMock()
        host.runs.read_autopilot_run.return_value = {
            "route_index": 0,
            "current_route": "scene-development",
            "consecutive_revisions": 0,
        }
        host._advance_lean_scene.return_value = True
        policy_value = default_policy("full_auto")
        policy_value["literary_kernel"] = "lean-v2"
        loop = ClaimedRunLoop(
            host,
            run_id="autopilot-lean",
            project=Path("project"),
            policy=DelegationPolicy(policy_value),
            steward=MagicMock(),
            stop=threading.Event(),
            route_order=("scene-development",),
            dependency_probe=lambda _project: False,
        )
        loop._enter_route = lambda run, route_index: RouteCycle(
            route_index,
            "scene-development",
            "scene-development",
            False,
            "owner",
        )
        loop._proactive_choice_stopped = lambda cycle: False

        loop.run()

        host._advance_lean_scene.assert_called_once()
        host._worker.assert_not_called()

    def test_autopilot_host_records_commit_and_advances_ready_route(self):
        class Steps:
            def __init__(self):
                self.values = [
                    LeanSceneStep(
                        "committed",
                        "scene_0001",
                        "scene-tx-1",
                        "committed",
                        committed=True,
                    ),
                    LeanSceneStep("route-ready", route_ready=True),
                ]

            def advance_one(self, **kwargs):
                return self.values.pop(0)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            store = JobStore(root / "studio.sqlite3")
            payload = default_policy("full_auto")
            payload["literary_kernel"] = "lean-v2"
            run = store.create_autopilot_run(
                str(project.resolve()),
                mode="full_auto",
                runtime="pi-worker",
                policy=payload,
            )
            store.update_autopilot_run(
                run["run_id"],
                current_route="scene-development",
                route_index=4,
            )
            service = AutopilotService(
                {
                    "application": {"data_root": str(root)},
                    "agent_runtime_roles": {"worker": "pi-worker", "reviewer": "pi-worker"},
                },
                store,
            )
            steps = Steps()
            service._lean_scene_coordinator = lambda run_id, project_root: steps
            policy = DelegationPolicy(payload)

            self.assertFalse(service._advance_lean_scene(run["run_id"], project, policy))
            after_commit = store.read_autopilot_run(run["run_id"])
            self.assertEqual(after_commit["tasks_completed"], 1)
            self.assertIn("scene_0001", after_commit["current_task_id"])

            self.assertFalse(service._advance_lean_scene(run["run_id"], project, policy))
            after_ready = store.read_autopilot_run(run["run_id"])
            self.assertEqual(after_ready["route_index"], 5)
            self.assertEqual(after_ready["current_task_id"], "")


if __name__ == "__main__":
    unittest.main()
