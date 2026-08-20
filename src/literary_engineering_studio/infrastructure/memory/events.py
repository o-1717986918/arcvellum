"""Explicit durable-event composition over memory aggregates."""

from __future__ import annotations

from typing import Any


class InMemoryDurableEventStore:
    def __init__(self, jobs, autopilot):
        self._jobs = jobs
        self._autopilot = autopilot

    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._jobs.append_event(job_id, event_type, data)

    def events_since(self, job_id: str, after: int = 0, *, limit: int = 200) -> list[dict[str, Any]]:
        return self._jobs.events_since(job_id, after, limit=limit)

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._autopilot.append_autopilot_event(run_id, event, data)

    def autopilot_events_since(
        self,
        run_id: str,
        after: int = 0,
        *,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        return self._autopilot.autopilot_events_since(run_id, after, limit=limit)


__all__ = ["InMemoryDurableEventStore"]
