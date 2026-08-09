from __future__ import annotations

import threading
import time
import unittest

from literary_engineering_studio.runtimes.opencode import _wait_for_session
from literary_engineering_studio.runtimes.opencode_session import (
    OpenCodeRole,
    session_timeout_policy,
)


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

    def test_busy_status_does_not_count_as_a_public_first_event(self):
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 5,
            threading.Event(),
            first_event_timeout=0.01,
            inter_event_timeout=10,
            has_public_activity=lambda: False,
            started_at=time.monotonic() - 1,
            last_activity=time.monotonic,
        )
        self.assertEqual(status, "first_event_timeout")

    def test_public_activity_switches_to_the_inter_event_limit(self):
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 5,
            threading.Event(),
            first_event_timeout=10,
            inter_event_timeout=0.01,
            has_public_activity=lambda: True,
            started_at=time.monotonic(),
            last_activity=lambda: time.monotonic() - 1,
        )
        self.assertEqual(status, "idle_timeout")

    def test_reasoning_liveness_prevents_false_first_event_timeout(self):
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 0.03,
            threading.Event(),
            first_event_timeout=0.01,
            inter_event_timeout=10,
            has_runtime_activity=lambda: True,
            has_productive_activity=lambda: False,
            started_at=time.monotonic() - 1,
            last_activity=time.monotonic,
        )
        self.assertEqual(status, "timeout")

    def test_runtime_activity_that_stops_trips_inter_event_timeout(self):
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 5,
            threading.Event(),
            first_event_timeout=10,
            inter_event_timeout=0.01,
            has_runtime_activity=lambda: True,
            has_productive_activity=lambda: False,
            started_at=time.monotonic(),
            last_activity=lambda: time.monotonic() - 1,
        )
        self.assertEqual(status, "idle_timeout")

    def test_productive_stall_diagnostic_is_emitted_once_without_stopping_liveness(self):
        diagnostics = []
        status = _wait_for_session(
            _BusyClient(),
            "session",
            time.monotonic() + 0.05,
            threading.Event(),
            first_event_timeout=0.01,
            inter_event_timeout=10,
            has_runtime_activity=lambda: True,
            has_productive_activity=lambda: False,
            on_productive_stall=diagnostics.append,
            started_at=time.monotonic() - 1,
            last_activity=time.monotonic,
        )
        self.assertEqual(status, "timeout")
        self.assertEqual(len(diagnostics), 1)

    def test_role_profile_takes_precedence_over_stale_legacy_timeout(self):
        policy = session_timeout_policy(
            {
                "session_idle_timeout_seconds": 120,
                "session_timeout_profiles": {
                    "default": {"first_event_seconds": 180, "inter_event_seconds": 300},
                    "reviewer": {"first_event_seconds": 240, "inter_event_seconds": 360},
                },
            },
            OpenCodeRole.REVIEWER,
        )
        self.assertEqual(policy.first_event_seconds, 240)
        self.assertEqual(policy.inter_event_seconds, 360)


if __name__ == "__main__":
    unittest.main()
