from __future__ import annotations

import unittest

from literary_engineering_studio.observability.runtime_event_timings import recover_event_timings


class RuntimeEventTimingsTests(unittest.TestCase):
    def test_recovers_phase_and_total_timings(self) -> None:
        events = [
            {"event": "runtime_started", "at": "2026-08-10T00:00:00+00:00"},
            {"event": "runner.ready", "at": "2026-08-10T00:00:00.010000+00:00"},
            {"event": "runner.reasoning.activity", "at": "2026-08-10T00:00:00.120000+00:00"},
            {"event": "tool.started", "at": "2026-08-10T00:00:01+00:00"},
            {"event": "file.changed", "at": "2026-08-10T00:00:01.500000+00:00"},
            {"event": "runtime_finished", "at": "2026-08-10T00:00:02+00:00"},
        ]

        timings = recover_event_timings(events, "")

        self.assertEqual(timings["time_to_process_ready_ms"], 10)
        self.assertEqual(timings["time_to_first_event_ms"], 10)
        self.assertEqual(timings["time_to_first_reasoning_ms"], 120)
        self.assertEqual(timings["time_to_first_tool_ms"], 1000)
        self.assertEqual(timings["time_to_first_output_ms"], 1500)
        self.assertEqual(timings["total_ms"], 2000)

    def test_uses_manifest_start_when_runtime_start_is_absent(self) -> None:
        timings = recover_event_timings(
            [{"event": "agent.message.completed", "at": "2026-08-10T00:00:01+00:00"}],
            "2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(timings["time_to_first_event_ms"], 1000)
        self.assertEqual(timings["time_to_first_text_ms"], 1000)
        self.assertNotIn("total_ms", timings)


if __name__ == "__main__":
    unittest.main()
