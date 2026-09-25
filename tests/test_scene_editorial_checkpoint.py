from types import SimpleNamespace
import threading
import unittest

from literary_engineering_studio.automation.controller import AutopilotService
from literary_engineering_studio.automation.lean_scene_host import LeanSceneAutopilotHost
from literary_engineering_studio.automation.policy import DelegationPolicy, default_policy
from literary_engineering_studio.project_agent.prompt_policy import delegated_scene_checkpoint_prompt


class _Runs:
    def __init__(self):
        self.advanced = []

    def advance_autopilot_run(self, run_id, **fields):
        self.advanced.append((run_id, fields))


class _PausedRuns:
    def __init__(self):
        self.run = {"run_id": "run-1", "status": "paused", "stop_reason": "scene-editorial-checkpoint"}

    def read_autopilot_run(self, _run_id):
        return dict(self.run)

    def update_autopilot_run(self, _run_id, **fields):
        self.run.update(fields)

    def append_autopilot_event(self, *_args):
        pass


class SceneEditorialCheckpointTests(unittest.TestCase):
    def test_managed_scene_commit_pauses_before_next_scene(self):
        runs = _Runs()
        pauses = []
        host = LeanSceneAutopilotHost(
            config={}, runs=runs, scene_transactions=None, execution_coordinator=None,
            emit_event=lambda *_args: None,
            pause=lambda *args: pauses.append(args),
        )
        policy = default_policy("full_auto", literary_kernel="lean-v2")
        policy["editorial_scene_checkpoint"] = True
        step = SimpleNamespace(
            route_ready=False, waiting_human=False, blocked=False, committed=True,
            scene_id="scene_0003", transaction_status="committed",
        )

        stopped = host._apply_step("run-1", {}, step, policy=DelegationPolicy(policy))

        self.assertTrue(stopped)
        self.assertEqual(runs.advanced[0][1]["current_task_id"], "lean-scene:scene_0003:committed")
        self.assertEqual(pauses[0][1], "scene-editorial-checkpoint")

    def test_unmanaged_run_does_not_pause(self):
        runs = _Runs()
        pauses = []
        host = LeanSceneAutopilotHost(
            config={}, runs=runs, scene_transactions=None, execution_coordinator=None,
            emit_event=lambda *_args: None, pause=lambda *args: pauses.append(args),
        )
        step = SimpleNamespace(
            route_ready=False, waiting_human=False, blocked=False, committed=True,
            scene_id="scene_0003", transaction_status="committed",
        )
        self.assertFalse(host._apply_step("run-1", {}, step, policy=DelegationPolicy(default_policy("full_auto"))))
        self.assertEqual(pauses, [])

    def test_checkpoint_prompt_checks_actual_prose_and_future_only(self):
        prompt = delegated_scene_checkpoint_prompt(
            "继续写三场", {"run_id": "r", "status": "paused", "stop_reason": "scene-editorial-checkpoint"},
        )
        self.assertIn("实际正文", prompt)
        self.assertIn("不回改已提交正文", prompt)
        self.assertIn('project_goal_manage(operation="recover", expected_stop_reason="scene-editorial-checkpoint")', prompt)

    def test_manual_pause_replaces_pending_editorial_checkpoint(self):
        runs = _PausedRuns()
        service = SimpleNamespace(runs=runs, _lock=threading.Lock(), _stops={})

        paused = AutopilotService.pause(service, "run-1", reason="user-request")

        self.assertEqual(paused["stop_reason"], "user-request")


if __name__ == "__main__":
    unittest.main()
