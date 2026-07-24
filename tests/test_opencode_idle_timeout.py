from __future__ import annotations

import threading
import time
import unittest

from literary_engineering_studio.runtimes.opencode import _wait_for_session


class _BusyClient:
    def session_status(self):
        return {"session": {"type": "busy"}}

    def abort(self, _session_id: str) -> None:
        return None


class OpenCodeIdleTimeoutTests(unittest.TestCase):
    def test_busy_session_without_activity_trips_idle_timeout_before_total_timeout(self):
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 5,
            threading.Event(),
            idle_timeout=0.01,
            last_activity=lambda: time.monotonic() - 1,
        )
        self.assertEqual(status, "idle_timeout")


if __name__ == "__main__":
    unittest.main()
