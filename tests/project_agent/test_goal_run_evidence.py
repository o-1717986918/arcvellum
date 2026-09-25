from __future__ import annotations

import unittest

from literary_engineering_studio.api.project_agent_composition import _goal_event_evidence
from literary_engineering_studio.project_agent.delegated_goal import goal_snapshot


class GoalRunEvidenceTests(unittest.TestCase):
    def test_committed_interaction_and_actual_revision_count_reach_top_agent(self):
        events = [
            {"event": "worker.scene.performance.environment", "data": {
                "scene_transaction_id": "tx-1", "passages": 4}},
            {"event": "worker.scene.performance.interaction.turn", "data": {
                "scene_transaction_id": "tx-1", "turn": 1, "speaker": "顾潮", "entries": 2}},
            {"event": "worker.scene.performance.interaction.turn", "data": {
                "scene_transaction_id": "tx-1", "turn": 1, "speaker": "顾潮", "entries": 2}},
            {"event": "worker.scene.performance.interaction.turn", "data": {
                "scene_transaction_id": "tx-1", "turn": 2, "speaker": "林未", "entries": 1}},
            {"event": "worker.scene.revised", "data": {
                "scene_id": "scene_0001", "revision_attempts": 1}},
            {"event": "worker.scene.committed", "data": {
                "scene_transaction_id": "tx-1", "scene_id": "scene_0001"}},
            {"event": "worker.scene.performance.interaction.turn", "data": {
                "scene_transaction_id": "tx-uncommitted", "turn": 1, "speaker": "旁人", "entries": 2}},
        ]
        evidence = _goal_event_evidence(events)
        snapshot = goal_snapshot({"run_id": "goal-1", "status": "paused", **evidence})

        self.assertEqual(snapshot["revision_summary"]["total_attempts"], 1)
        self.assertEqual(snapshot["scene_performance_summary"], {
            "committed_interaction_scenes": 1,
            "interaction_turns": 2,
            "actor_entries": 3,
            "speakers": ["林未", "顾潮"],
            "environment_passages": 4,
        })


if __name__ == "__main__":
    unittest.main()
