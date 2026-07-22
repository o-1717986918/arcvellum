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
        )
        self.assertEqual(projection["status"], "active")
        self.assertEqual(projection["active_task"]["stage"], "主创正在工作")
        self.assertNotIn("C:/projects/example", projection["recent_events"][0]["message"])
        self.assertEqual(projection["sessions"][0]["role"], "主创执行者")


if __name__ == "__main__":
    unittest.main()
