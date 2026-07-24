"""Bounded in-memory event channels for high-frequency, non-durable UI updates."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any


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


EPHEMERAL_WORKER_EVENTS = {"agent.message.delta", "runner.session.status"}


def coalesce_live_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if (
            result
            and item.get("event") == "agent.message.delta"
            and result[-1].get("event") == "agent.message.delta"
        ):
            previous = result[-1]
            previous_data = previous.get("data") if isinstance(previous.get("data"), dict) else {}
            current_data = item.get("data") if isinstance(item.get("data"), dict) else {}
            previous_data["text"] = str(previous_data.get("text") or "") + str(current_data.get("text") or "")
            previous["sequence"] = item.get("sequence")
            previous["at"] = item.get("at")
        else:
            result.append({**item, "data": dict(item.get("data") or {})})
    return result
