from __future__ import annotations

import json
import unittest

from literary_engineering_studio.runtimes.opencode_event_observer import (
    OpenCodeEventObserver,
)
from literary_engineering_studio.runtimes.opencode_timing import OpenCodeTiming


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class OpenCodeEventObserverTests(unittest.TestCase):
    def test_reasoning_lifecycle_is_content_free_and_productive_output_closes_it(self):
        clock = _Clock()
        events = []
        runtime_marks = []
        observer = OpenCodeEventObserver(
            session_id="session-1",
            timing=OpenCodeTiming(started_at=clock()),
            emit=lambda event, data: events.append((event, data)),
            mark_activity=lambda: runtime_marks.append(clock()),
            errors=[],
            clock=clock,
            reasoning_pulse_seconds=5,
        )

        observer.accept(
            "runner.reasoning.activity",
            {"session_id": "session-1", "delta_events": 1, "delta_characters": 17},
        )
        clock.value += 6
        observer.accept(
            "runner.reasoning.activity",
            {"session_id": "session-1", "delta_events": 1, "delta_characters": 9},
        )
        observer.accept(
            "agent.message.delta",
            {"session_id": "session-1", "text": "visible"},
        )

        names = [name for name, _ in events]
        self.assertIn("runner.first_activity", names)
        self.assertIn("runner.reasoning.started", names)
        self.assertIn("runner.reasoning.activity", names)
        self.assertIn("runner.reasoning.completed", names)
        self.assertIn("runner.first_event", names)
        self.assertTrue(observer.runtime_activity)
        self.assertTrue(observer.productive_activity)
        self.assertEqual(len(runtime_marks), 3)
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("private", serialized)
        completed = next(data for name, data in events if name == "runner.reasoning.completed")
        self.assertEqual(completed["total_events"], 2)
        self.assertEqual(completed["total_characters"], 26)


if __name__ == "__main__":
    unittest.main()
