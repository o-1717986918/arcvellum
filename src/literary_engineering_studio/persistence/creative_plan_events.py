"""Append-only events for creative plan revisions and activation."""

from __future__ import annotations

import json
from typing import Any

from .creative_plan_primitives import validate_plan_id
from .primitives import _json, _now


CREATIVE_PLAN_EVENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS creative_plan_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    at TEXT NOT NULL,
    data_json TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES creative_plans(plan_id)
);
CREATE INDEX IF NOT EXISTS creative_plan_events_plan_idx
    ON creative_plan_events(plan_id, sequence);
"""


class CreativePlanEventStoreMixin:
    def creative_plan_events(
        self,
        plan_id: str,
        *,
        after: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        validate_plan_id(plan_id)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM creative_plan_events
                WHERE plan_id = ? AND sequence > ?
                ORDER BY sequence ASC LIMIT ?
                """,
                (plan_id, max(0, int(after)), max(1, min(1000, int(limit)))),
            ).fetchall()
        return [_event_row(row) for row in rows]


def append_creative_plan_event_tx(
    connection,
    plan_id: str,
    revision: int,
    event_type: str,
    data: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO creative_plan_events (
            plan_id, revision, event_type, at, data_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (plan_id, revision, event_type, _now(), _json(data)),
    )


def _event_row(row) -> dict[str, Any]:
    payload = dict(row)
    payload["data"] = json.loads(str(payload.pop("data_json") or "{}"))
    payload["event"] = payload.pop("event_type")
    return payload
