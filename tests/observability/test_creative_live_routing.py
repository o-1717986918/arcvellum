from __future__ import annotations

import unittest

from literary_engineering_studio.automation.controller import _runtime_event_context
from literary_engineering_studio.observability.creative_live.contracts import project_channel
from literary_engineering_studio.observability.live_events import LiveEventBus


class CreativeLiveRoutingTests(unittest.TestCase):
    def test_autopilot_runtime_context_is_stable_and_non_destructive(self):
        original = {"session_id": "session-1", "text": "片段"}
        run = {
            "run_id": "run-1",
            "current_task_id": "task-1",
            "current_route": "scene-development",
            "runtime": "pi-worker",
        }

        enriched = _runtime_event_context(run, "agent.message.delta", original)

        self.assertEqual(original, {"session_id": "session-1", "text": "片段"})
        self.assertEqual(enriched["task_id"], "task-1")
        self.assertEqual(enriched["route"], "scene-development")
        self.assertEqual(enriched["attempt_id"], "run-1")

    def test_project_channel_carries_multiple_runtime_sources(self):
        bus = LiveEventBus()
        channel = project_channel(".")
        bus.publish(channel, "agent.message.delta", {"controller_id": "job-1"})
        bus.publish(channel, "artifact.preview.snapshot", {"controller_id": "run-1"})

        events = bus.wait_since(channel, 0, timeout=0)

        self.assertEqual([item["sequence"] for item in events], [1, 2])
        self.assertEqual(
            [item["event"] for item in events],
            ["agent.message.delta", "artifact.preview.snapshot"],
        )


if __name__ == "__main__":
    unittest.main()
