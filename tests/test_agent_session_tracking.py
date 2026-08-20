from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from literary_engineering_studio.agent_session_tracking import (
    AgentSessionEventProjector,
    track_agent_session_event,
)
from literary_engineering_studio.jobs import JobStore


class AgentSessionTrackingTests(unittest.TestCase):
    def test_named_projector_routes_mutation_without_a_compatibility_facade(self):
        sessions = Mock()
        context_ledgers = Mock()
        mutation_receipts = Mock()
        mutation_receipts.record_mutation_receipt.return_value = {"receipt_id": "receipt-one"}
        observed = []
        projector = AgentSessionEventProjector(
            sessions,
            context_ledgers,
            mutation_receipts,
            mutation_listener=lambda project, receipt: observed.append((project, receipt)),
        )

        result = projector(
            project_root="C:/work",
            role="worker",
            runtime="pi-worker",
            controller_id="run-one",
            event="mutation.receipt",
            data={"receipt": {"receipt_id": "receipt-one"}},
        )

        self.assertIsNone(result)
        mutation_receipts.record_mutation_receipt.assert_called_once()
        context_ledgers.record_context_ledger.assert_not_called()
        sessions.upsert_agent_session.assert_not_called()
        self.assertEqual(observed, [("C:/work", {"receipt_id": "receipt-one"})])

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

    def test_preserves_context_ledger_binding_across_later_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            common = {
                "project_root": "C:/work",
                "role": "worker",
                "runtime": "opencode",
                "controller_id": "run-ledger",
                "task_id": "task-ledger",
                "route": "scene-development",
            }
            track_agent_session_event(
                store,
                **common,
                event="runner.session.created",
                data={
                    "session_id": "session-ledger-binding",
                    "context_ledger_id": "context-1234567890abcdef",
                    "context_ledger_digest": "a" * 64,
                },
            )
            track_agent_session_event(
                store,
                **common,
                event="runner.session.started",
                data={"session_id": "session-ledger-binding"},
            )

            session = store.read_agent_session("session-ledger-binding")
            self.assertEqual(session["context_ledger_id"], "context-1234567890abcdef")
            self.assertEqual(session["context_ledger_digest"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
