from __future__ import annotations

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
        )
        self.assertEqual(projection["status"], "active")
        self.assertEqual(projection["schema"], "arcvellum/agent-observability/v2")
        self.assertEqual(projection["active_task"]["stage"], "主创正在工作")
        self.assertNotIn("C:/projects/example", projection["recent_events"][0]["message"])
        self.assertEqual(projection["sessions"][0]["role"], "主创执行者")
        self.assertEqual(projection["sessions"][0]["retry_count"], 1)
        self.assertEqual(projection["services"][0]["status"], "busy")
        self.assertNotIn("profile_path", projection["services"][0])

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
