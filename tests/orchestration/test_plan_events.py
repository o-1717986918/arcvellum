from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.orchestration import (
    CREATIVE_PLAN_EVENT_SCHEMA,
    CreativePlanEvent,
    CreativePlanEventType,
    completed_candidate_from_event,
    parse_creative_plan_event,
)
from literary_engineering_studio.persistence.creative_plan_events import (
    append_creative_plan_event_tx,
)

from tests.orchestration.fixtures import scene_plan_candidate
from tests.orchestration.plan_persistence_support import persist_ready_record


class CreativePlanEventTests(unittest.TestCase):
    def test_delta_is_display_only_and_cannot_cross_the_lint_boundary(self):
        event = CreativePlanEvent(
            event_type=CreativePlanEventType.CANDIDATE_DELTA,
            plan_id="plan-event-delta",
            revision=1,
            session_id="planner-session-a",
            sequence=3,
            data={"text": '{"objective":'},
        )

        self.assertTrue(event.display_only)
        self.assertEqual(parse_creative_plan_event(event.as_dict()), event)
        with self.assertRaisesRegex(ValueError, "completed candidate"):
            completed_candidate_from_event(event)

    def test_completed_candidate_is_the_only_typed_lint_input(self):
        candidate = scene_plan_candidate()
        event = CreativePlanEvent(
            event_type=CreativePlanEventType.CANDIDATE_COMPLETED,
            plan_id="plan-event-complete",
            revision=1,
            session_id="planner-session-a",
            sequence=7,
            data={"candidate": candidate},
        )

        self.assertFalse(event.display_only)
        self.assertEqual(completed_candidate_from_event(event), candidate)
        forged = event.as_dict()
        forged["display_only"] = True
        with self.assertRaisesRegex(ValueError, "machine-owned"):
            parse_creative_plan_event(forged)

    def test_store_rejects_display_delta_and_returns_typed_durable_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            persist_ready_record(store, root, "plan-event-store")

            with store._write_lock, store._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(ValueError, "display-only"):
                    append_creative_plan_event_tx(
                        connection,
                        "plan-event-store",
                        1,
                        CreativePlanEventType.CANDIDATE_DELTA,
                        {"text": "partial"},
                        session_id="planner-session-a",
                        at="2026-08-20T00:00:00+00:00",
                    )

            events = store.creative_plan_events("plan-event-store")
            self.assertEqual(len(events), 2)
            self.assertTrue(
                all(item["schema"] == CREATIVE_PLAN_EVENT_SCHEMA for item in events)
            )
            self.assertTrue(all(item["display_only"] is False for item in events))
            self.assertTrue(all(item["session_id"] == "studio-store" for item in events))

    def test_unknown_event_name_is_rejected_before_sql(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            with store._write_lock, store._connection() as connection:
                with self.assertRaises(ValueError):
                    append_creative_plan_event_tx(
                        connection,
                        "plan-does-not-matter",
                        1,
                        "plan.agent-invented-shortcut",
                        {},
                        at="2026-08-20T00:00:00+00:00",
                    )


if __name__ == "__main__":
    unittest.main()
