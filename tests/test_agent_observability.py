from __future__ import annotations

from datetime import datetime, timezone
import unittest

from literary_engineering_studio.agent_observability import build_agent_observability


class AgentObservabilityTests(unittest.TestCase):
    def test_projects_visible_stages_without_paths_or_hidden_reasoning(self):
        projection = build_agent_observability(
            "C:/projects/example",
            {"run": {"run_id": "run-1", "runtime": "opencode", "status": "running", "current_route": "scene-development", "current_task_id": "task-7", "tasks_completed": 2, "failures": 0}},
            [{"sequence": 4, "event": "worker.runner.started", "at": "2026-07-22T00:00:00Z", "data": {"task_id": "task-7"}}],
            {"current_task": {"route": "scene-development"}},
            [{
                "session_id": "ses_1234567890abcdef",
                "role": "worker",
                "runtime": "opencode",
                "model": "deepseek/deepseek-chat",
                "status": "running",
                "route": "scene-development",
                "task_id": "task-7",
                "event_count": 3,
                "retry_count": 1,
                "last_event": "runner.session.started",
                "last_message": "主创正在执行当前正式任务。",
                "started_at": "2026-07-22T00:00:00+00:00",
                "updated_at": "2026-07-22T00:00:02+00:00",
                "finished_at": "",
            }],
            [{
                "role": "worker",
                "model": "deepseek/deepseek-chat",
                "active_leases": 1,
                "restart_count": 0,
                "healthy": True,
                "started_at": "2026-07-22T00:00:00+00:00",
                "profile_path": "C:/private/profile",
            }],
            now=datetime(2026, 7, 22, 0, 0, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(projection["status"], "active")
        self.assertEqual(projection["schema"], "arcvellum/agent-observability/v2")
        self.assertEqual(projection["active_task"]["stage"], "主创正在工作")
        self.assertNotIn("C:/projects/example", projection["recent_events"][0]["message"])
        self.assertEqual(projection["sessions"][0]["role"], "主创执行者")
        self.assertEqual(projection["sessions"][0]["retry_count"], 1)
        self.assertEqual(projection["services"][0]["status"], "busy")
        self.assertNotIn("profile_path", projection["services"][0])

    def test_marks_running_controller_stalled_after_no_verifiable_activity(self):
        projection = build_agent_observability(
            "C:/projects/example",
            {
                "run": {
                    "run_id": "run-1",
                    "runtime": "opencode",
                    "status": "running",
                    "current_route": "scene-development",
                    "current_task_id": "task-7",
                    "last_progress_at": "2026-07-22T00:00:00Z",
                }
            },
            [],
            {"current_task": {"route": "scene-development"}},
            [],
            [],
            now=datetime(2026, 7, 22, 0, 5, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(projection["status"], "stalled")
        self.assertEqual(projection["active_task"]["status"], "stalled")
        self.assertTrue(projection["controller"]["stalled"])
        self.assertEqual(projection["controller"]["last_activity_at"], "2026-07-22T00:00:00Z")

    def test_paused_controller_does_not_report_historical_running_session_as_live(self):
        projection = build_agent_observability(
            "C:/projects/example",
            {"run": {"run_id": "run-1", "status": "paused", "runtime": "opencode"}},
            [],
            {"current_task": {}},
            [{
                "session_id": "session-worker-123456789",
                "role": "worker",
                "runtime": "opencode",
                "status": "running",
                "started_at": "2026-07-22T00:00:00Z",
                "updated_at": "2026-07-22T00:00:01Z",
            }],
            [],
        )

        self.assertEqual(projection["status"], "idle")
        self.assertEqual(projection["active_task"]["status"], "paused")

    def test_marks_abandoned_live_session_as_interrupted_without_hiding_history(self):
        projection = build_agent_observability(
            "C:/projects/example",
            {"run": {"run_id": "run-1", "status": "running", "runtime": "opencode"}},
            [],
            {"current_task": {}},
            [{
                "session_id": "session-worker-123456789",
                "role": "worker",
                "runtime": "opencode",
                "status": "running",
                "started_at": "2026-07-22T00:00:00Z",
                "updated_at": "2026-07-22T00:00:01Z",
            }],
            [],
            now=datetime(2026, 7, 22, 0, 6, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(projection["sessions"][0]["status"], "interrupted")
        self.assertIn("长时间未报告活动", projection["sessions"][0]["last_message"])

    def test_keeps_worker_advisor_and_steward_as_separate_sessions(self):
        sessions = [
            {
                "session_id": f"session-{role}-123456789",
                "role": role,
                "runtime": "opencode",
                "model": f"provider/{role}",
                "status": "running" if role != "advisor" else "idle",
                "route": "scene-development",
                "task_id": "task-1",
                "event_count": 2,
                "retry_count": 0,
                "last_event": "runner.session.started",
                "last_message": "",
                "started_at": "2026-07-22T00:00:00+00:00",
                "updated_at": "2026-07-22T00:00:01+00:00",
                "finished_at": "",
            }
            for role in ("worker", "advisor", "steward")
        ]
        projection = build_agent_observability(
            "C:/projects/example",
            {"run": {}},
            [],
            {"current_task": {}},
            sessions,
            [],
        )
        self.assertEqual(
            [item["role"] for item in projection["sessions"]],
            ["主创执行者", "项目顾问", "受托决策者"],
        )
        self.assertEqual(len({item["session_id"] for item in projection["sessions"]}), 3)


if __name__ == "__main__":
    unittest.main()
