import unittest

from literary_engineering_studio.live_events import EPHEMERAL_WORKER_EVENTS, coalesce_live_events
from literary_engineering_studio.observability.event_policy import should_persist_runtime_event
from literary_engineering_studio.runtime_events import normalize_opencode_event


def _tool_event(status: str):
    return {
        "type": "message.part.updated",
        "properties": {
            "part": {
                "type": "tool",
                "tool": "write",
                "callID": "call-1",
                "state": {"status": status},
            }
        },
    }


class RuntimeEventTests(unittest.TestCase):
    def test_tool_transitions_are_deduplicated_by_call_id(self):
        states = {}
        self.assertEqual(normalize_opencode_event(_tool_event("pending"), tool_states=states)[0][0], "tool.started")
        self.assertEqual(normalize_opencode_event(_tool_event("running"), tool_states=states), ())
        self.assertEqual(normalize_opencode_event(_tool_event("completed"), tool_states=states)[0][0], "tool.completed")
        self.assertEqual(normalize_opencode_event(_tool_event("completed"), tool_states=states), ())

    def test_adjacent_text_deltas_are_coalesced(self):
        result = coalesce_live_events(
            [
                {"sequence": 1, "event": "agent.message.delta", "at": "a", "data": {"text": "你"}},
                {"sequence": 2, "event": "agent.message.delta", "at": "b", "data": {"text": "好"}},
                {"sequence": 3, "event": "tool.started", "at": "c", "data": {"tool": "write"}},
            ]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["data"]["text"], "你好")
        self.assertEqual(result[0]["sequence"], 2)

    def test_reasoning_activity_is_content_free_ephemeral_and_coalesced(self):
        normalized = normalize_opencode_event(
            {
                "type": "message.part.updated",
                "properties": {
                    "delta": "private reasoning",
                    "part": {"type": "reasoning", "sessionID": "session-1"},
                },
            }
        )
        self.assertEqual(normalized[0][0], "runner.reasoning.activity")
        self.assertEqual(normalized[0][1]["delta_characters"], len("private reasoning"))
        self.assertNotIn("private reasoning", str(normalized))
        self.assertIn("runner.reasoning.activity", EPHEMERAL_WORKER_EVENTS)
        self.assertFalse(should_persist_runtime_event("runner.reasoning.activity"))

        result = coalesce_live_events(
            [
                {
                    "sequence": 1,
                    "event": "runner.reasoning.activity",
                    "at": "a",
                    "data": {"delta_events": 1, "delta_characters": 4, "total_events": 1},
                },
                {
                    "sequence": 2,
                    "event": "runner.reasoning.activity",
                    "at": "b",
                    "data": {"delta_events": 1, "delta_characters": 6, "total_events": 2},
                },
            ]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["data"]["delta_characters"], 10)
        self.assertEqual(result[0]["data"]["total_events"], 2)


if __name__ == "__main__":
    unittest.main()
