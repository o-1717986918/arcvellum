from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import unittest

from literary_engineering_studio.runtimes.base import RuntimeResult
from literary_engineering_studio.runtimes.opencode_timing import OpenCodeTiming, attach_timing


class OpenCodeTimingTests(unittest.TestCase):
    def test_first_mark_wins_and_metadata_contains_no_content(self):
        with patch("literary_engineering_studio.runtimes.opencode_timing.time.monotonic", side_effect=[10.2, 10.5]):
            timing = OpenCodeTiming(started_at=10.0)
            self.assertEqual(timing.mark("reasoning"), 200)
            self.assertEqual(timing.mark("reasoning"), 200)
            metadata = timing.metadata()
        self.assertEqual(metadata["time_to_first_reasoning_ms"], 200)
        self.assertEqual(metadata["total_ms"], 500)
        self.assertNotIn("text", metadata)

    def test_attach_timing_preserves_failure_metadata(self):
        with patch("literary_engineering_studio.runtimes.opencode_timing.time.monotonic", side_effect=[20.1, 20.3]):
            timing = OpenCodeTiming(started_at=20.0)
            timing.mark("prompt_submitted")
            result = attach_timing(
                RuntimeResult("opencode", "timeout", None, (), Path("out"), "timeout", {"failure_kind": "idle_timeout"}),
                timing,
            )
        self.assertEqual(result.metadata["failure_kind"], "idle_timeout")
        self.assertEqual(result.metadata["time_to_prompt_submitted_ms"], 100)
        self.assertEqual(result.metadata["total_ms"], 300)


if __name__ == "__main__":
    unittest.main()
