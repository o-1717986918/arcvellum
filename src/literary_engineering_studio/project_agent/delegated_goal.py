"""Observe a delegated Autopilot goal without keeping an Agent process alive."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import threading
import time
from typing import Any


TERMINAL_GOAL_STATUSES = frozenset({"complete", "paused", "blocked", "cancelled", "failed"})
WAITING_GOAL_OPERATIONS = frozenset({"goal_start", "goal_resume", "goal_recover"})

GoalRunReader = Callable[[str], Mapping[str, Any]]
GoalEventSink = Callable[[str, dict[str, Any]], None]
Heartbeat = Callable[[], None]


@dataclass(frozen=True)
class DelegatedGoal:
    """Small, non-secret binding between an Agent turn and an Autopilot run."""

    run_id: str
    work_id: str
    operation: str
    run_status: str

    @classmethod
    def from_tool_event(cls, event: str, data: Mapping[str, Any]) -> "DelegatedGoal | None":
        if event != "project_agent.tool.finished" or data.get("ok") is False:
            return None
        if str(data.get("name") or "") != "project_goal_manage":
            return None
        receipt = data.get("receipt")
        if not isinstance(receipt, Mapping):
            return None
        run_id = str(receipt.get("run_id") or "").strip()
        operation = str(receipt.get("operation") or "").strip()
        if not run_id or operation not in WAITING_GOAL_OPERATIONS:
            return None
        return cls(
            run_id=run_id,
            work_id=str(receipt.get("work_id") or "").strip(),
            operation=operation,
            run_status=str(receipt.get("run_status") or "").strip(),
        )

    @property
    def needs_observation(self) -> bool:
        return self.run_status not in TERMINAL_GOAL_STATUSES


class DelegatedGoalObserver:
    """Wait for one durable goal while emitting only meaningful state changes."""

    def __init__(self, read_run: GoalRunReader, *, poll_interval: float = 0.5) -> None:
        if poll_interval <= 0:
            raise ValueError("goal poll interval must be positive")
        self._read_run = read_run
        self._poll_interval = poll_interval

    def wait(
        self,
        goal: DelegatedGoal,
        *,
        cancel_event: threading.Event | None,
        event_sink: GoalEventSink,
        heartbeat: Heartbeat | None = None,
    ) -> dict[str, Any] | None:
        last_fingerprint = ""
        heartbeat_at = 0.0
        while True:
            if cancel_event is not None and cancel_event.is_set():
                return None
            run = dict(self._read_run(goal.run_id))
            snapshot = goal_snapshot(run)
            fingerprint = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
            if fingerprint != last_fingerprint:
                event_sink("project_agent.goal.progress", snapshot)
                last_fingerprint = fingerprint
            status = str(snapshot.get("status") or "")
            if status in TERMINAL_GOAL_STATUSES:
                return run
            now = time.monotonic()
            if heartbeat is not None and now - heartbeat_at >= 20:
                heartbeat()
                heartbeat_at = now
            if cancel_event is not None:
                cancel_event.wait(self._poll_interval)
            else:
                time.sleep(self._poll_interval)


def goal_snapshot(run: Mapping[str, Any]) -> dict[str, Any]:
    """Expose useful progress without leaking a full internal run record."""

    snapshot = {
        "run_id": str(run.get("run_id") or ""),
        "status": str(run.get("status") or ""),
        "current_route": str(run.get("current_route") or ""),
        "current_task_id": str(run.get("current_task_id") or ""),
        "tasks_completed": int(run.get("tasks_completed") or 0),
        "failures": int(run.get("failures") or 0),
        "stop_reason": str(run.get("stop_reason") or ""),
        "last_error": str(run.get("last_error") or "")[:1000],
    }
    if chapter := _chapter_update(run.get("chapter_update")):
        snapshot["chapter_update"] = chapter
    if revisions := _revision_summary(run.get("revision_summary")):
        snapshot["revision_summary"] = revisions
    if performance := _scene_performance_summary(run.get("scene_performance_summary")):
        snapshot["scene_performance_summary"] = performance
    return snapshot


def _chapter_update(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    author = value.get("author_summary")
    return {
        "chapter_id": str(value.get("chapter_id") or ""),
        "message": str(value.get("message") or "")[:600],
        "author_summary": dict(author) if isinstance(author, Mapping) else {},
    }


def _revision_summary(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "total_attempts": int(value.get("total_attempts") or 0),
        "scene_count": int(value.get("scene_count") or 0),
        "max_attempts": int(value.get("max_attempts") or 0),
    }


def _scene_performance_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value.get("committed_interaction_scenes"):
        return {}
    speakers = value.get("speakers")
    return {
        "committed_interaction_scenes": int(value.get("committed_interaction_scenes") or 0),
        "interaction_turns": int(value.get("interaction_turns") or 0),
        "actor_entries": int(value.get("actor_entries") or 0),
        "speakers": [str(speaker) for speaker in speakers[:8]] if isinstance(speakers, list) else [],
        "environment_passages": int(value.get("environment_passages") or 0),
    }


__all__ = [
    "DelegatedGoal",
    "DelegatedGoalObserver",
    "TERMINAL_GOAL_STATUSES",
    "goal_snapshot",
]
