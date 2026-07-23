from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.agent_session_tracking import track_agent_session_event
from literary_engineering_studio.jobs import JobStore


class AgentSessionTrackingTests(unittest.TestCase):
    def test_tracks_real_lifecycle_and_ignores_stream_deltas(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            common = {
                "project_root": "C:/work",
                "role": "worker",
                "runtime": "opencode",
                "controller_id": "run-1",
                "task_id": "task-1",
                "route": "scene-development",
            }
            track_agent_session_event(
                store,
                **common,
                event="runner.session.created",
                data={"session_id": "session-123456"},
            )
            track_agent_session_event(
                store,
                **common,
                event="runner.session.started",
                data={"session_id": "session-123456", "model": "provider/model"},
            )
            before = store.read_agent_session("session-123456")
            self.assertIsNone(
                track_agent_session_event(
                    store,
                    **common,
                    event="agent.message.delta",
                    data={"session_id": "session-123456", "text": "private stream"},
                )
            )
            track_agent_session_event(
                store,
                **common,
                event="repair.started",
                data={"session_id": "session-123456", "attempt": 1},
            )
            track_agent_session_event(
                store,
                **common,
                event="runner.session.finished",
                data={"session_id": "session-123456", "status": "complete"},
            )
            final = store.read_agent_session("session-123456")
            self.assertEqual(before["event_count"] + 2, final["event_count"])
            self.assertEqual(final["status"], "complete")
            self.assertEqual(final["retry_count"], 1)
            self.assertNotIn("private stream", final["last_message"])


if __name__ == "__main__":
    unittest.main()
