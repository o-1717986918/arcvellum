import unittest

from literary_engineering_studio.live_events import coalesce_live_events
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


if __name__ == "__main__":
    unittest.main()
