"""Recover content-free phase timings from persisted runtime events."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping


_PHASE_EVENTS = {
    "time_to_process_ready_ms": frozenset({"runner.ready"}),
    "time_to_session_created_ms": frozenset({"runner.session.created"}),
    "time_to_prompt_submitted_ms": frozenset(
        {"runner.provider.request.started", "runner.prompt.submitted"}
    ),
    "time_to_first_reasoning_ms": frozenset(
        {"runner.reasoning.started", "runner.reasoning.activity"}
    ),
    "time_to_first_text_ms": frozenset({"agent.message.delta", "agent.message.completed"}),
    "time_to_first_tool_ms": frozenset({"tool.started"}),
    "time_to_first_output_ms": frozenset({"file.changed"}),
}
_BOUNDARY_EVENTS = frozenset({"runtime_started", "runtime_finished"})


def recover_event_timings(
    events: list[dict[str, object]],
    fallback_start: str,
) -> dict[str, int]:
    """Return available elapsed phase timings without exposing event content."""
    start = _first_at(events, {"runtime_started"}) or fallback_start
    result = _phase_timings(events, start)
    first_activity = _first_activity_at(events)
    if first_activity:
        result["time_to_first_event_ms"] = _elapsed_ms(start, first_activity)
    finished = _first_at(reversed(events), {"runtime_finished"})
    if finished:
        result["total_ms"] = _elapsed_ms(start, finished)
    return result


def _phase_timings(events: list[dict[str, object]], start: str) -> dict[str, int]:
    return {
        name: _elapsed_ms(start, at)
        for name, event_names in _PHASE_EVENTS.items()
        if (at := _first_at(events, event_names))
    }


def _first_activity_at(events: list[dict[str, object]]) -> str:
    return next(
        (
            str(item.get("at") or "")
            for item in events
            if item.get("event") not in _BOUNDARY_EVENTS and item.get("at")
        ),
        "",
    )


def _first_at(events: Iterable[Mapping[str, object]], names: set[str] | frozenset[str]) -> str:
    return next(
        (
            str(item.get("at") or "")
            for item in events
            if item.get("event") in names and item.get("at")
        ),
        "",
    )


def _elapsed_ms(start: str, end: str) -> int:
    try:
        left = datetime.fromisoformat(start.replace("Z", "+00:00"))
        right = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return 0
    return max(0, round((right - left).total_seconds() * 1000))


__all__ = ["recover_event_timings"]
