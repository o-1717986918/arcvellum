"""Bounded in-memory event channels for high-frequency, non-durable UI updates."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any

from .event_policy import EPHEMERAL_RUNTIME_EVENTS


@dataclass(frozen=True)
class LiveEvent:
    sequence: int
    event: str
    at: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "event": self.event, "at": self.at, "data": self.data}


class LiveEventBus:
    def __init__(self, *, max_events_per_channel: int = 800):
        self.max_events_per_channel = max(50, int(max_events_per_channel))
        self._channels: dict[str, deque[LiveEvent]] = {}
        self._sequences: dict[str, int] = {}
        self._condition = threading.Condition(threading.RLock())
        self._closed = False

    def publish(self, channel: str, event: str, data: dict[str, Any]) -> LiveEvent:
        with self._condition:
            sequence = self._sequences.get(channel, 0) + 1
            self._sequences[channel] = sequence
            item = LiveEvent(sequence, event, datetime.now(timezone.utc).isoformat(), dict(data))
            queue = self._channels.setdefault(channel, deque(maxlen=self.max_events_per_channel))
            queue.append(item)
            self._condition.notify_all()
            return item

    def notify(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def latest_sequence(self, channel: str) -> int:
        with self._condition:
            return self._sequences.get(channel, 0)

    def wait_since(self, channel: str, after: int, *, timeout: float = 0.5) -> list[dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while not self._closed:
                values = [item.as_dict() for item in self._channels.get(channel, ()) if item.sequence > after]
                if values:
                    return values
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(remaining)
            return []

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


EPHEMERAL_WORKER_EVENTS = set(EPHEMERAL_RUNTIME_EVENTS)


def coalesce_live_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if result and _merge_adjacent_event(result[-1], item):
            continue
        result.append({**item, "data": dict(item.get("data") or {})})
    return result


def _merge_adjacent_event(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    event = str(current.get("event") or "")
    if event != str(previous.get("event") or ""):
        return False
    previous_data = previous.get("data") if isinstance(previous.get("data"), dict) else {}
    current_data = current.get("data") if isinstance(current.get("data"), dict) else {}
    if event == "agent.message.delta":
        previous_data["text"] = str(previous_data.get("text") or "") + str(current_data.get("text") or "")
    elif event == "runner.reasoning.activity":
        _merge_reasoning_activity(previous_data, current_data)
    else:
        return False
    previous["sequence"] = current.get("sequence")
    previous["at"] = current.get("at")
    return True


def _merge_reasoning_activity(previous: dict[str, Any], current: dict[str, Any]) -> None:
    for key in ("delta_events", "delta_characters"):
        previous[key] = int(previous.get(key) or 0) + int(current.get(key) or 0)
    for key in ("total_events", "total_characters", "elapsed_ms"):
        previous[key] = max(int(previous.get(key) or 0), int(current.get(key) or 0))
