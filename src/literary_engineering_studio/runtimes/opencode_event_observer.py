"""Observe OpenCode events without retaining prompts or reasoning content."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable

from ..observability.runtime_events import merge_usage_summary, normalize_opencode_event
from .opencode_failures import normalize_model_warning
from .opencode_timing import OpenCodeTiming


@dataclass
class OpenCodeEventObserver:
    session_id: str
    timing: OpenCodeTiming
    emit: Callable[[str, dict[str, Any]], None]
    mark_activity: Callable[[], None]
    errors: list[str]
    clock: Callable[[], float] = time.monotonic
    reasoning_pulse_seconds: float = 5.0
    runtime_activity: bool = False
    productive_activity: bool = False
    usage_summary: dict[str, Any] = field(default_factory=dict)
    tool_states: dict[str, str] = field(default_factory=dict)
    reasoning_events: int = 0
    reasoning_characters: int = 0
    _reasoning_active: bool = False
    _reasoning_started_at: float = 0.0
    _last_reasoning_pulse_at: float = 0.0
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def public_activity(self) -> bool:
        """Compatibility alias for the old user-visible progress predicate."""

        return self.productive_activity

    def consume(self, client: Any, stop: threading.Event) -> None:
        try:
            for raw in client.events(stop):
                normalized = normalize_opencode_event(
                    raw,
                    session_id=self.session_id,
                    tool_states=self.tool_states,
                )
                for name, data in normalized:
                    self.accept(name, data)
        except (RuntimeError, OSError, TimeoutError) as exc:
            if not stop.is_set():
                self.emit(
                    "runner.warning",
                    {"session_id": self.session_id, "kind": "event-stream", "detail": str(exc)},
                )

    def accept(self, name: str, data: dict[str, Any]) -> None:
        event_session = str(data.get("session_id") or "")
        if not event_session or event_session == self.session_id:
            self.mark_activity()
            self._mark_runtime_activity()
        if name == "runner.reasoning.activity":
            self._accept_reasoning(data)
            return
        if name == "runner.session.status" and str(data.get("status") or "") in {"idle", "completed"}:
            self.finish_reasoning("session-idle")
        self._mark_productive_phase(name)
        if name == "usage.updated":
            merge_usage_summary(self.usage_summary, data)
        self.emit(name, normalize_model_warning(name, data, self.errors))

    def finish_reasoning(self, reason: str) -> None:
        with self._lock:
            if not self._reasoning_active:
                return
            elapsed_ms = max(0, round((self.clock() - self._reasoning_started_at) * 1000))
            self._reasoning_active = False
            payload = {
                "session_id": self.session_id,
                "total_events": self.reasoning_events,
                "total_characters": self.reasoning_characters,
                "elapsed_ms": elapsed_ms,
                "reason": reason,
            }
        self.emit("runner.reasoning.completed", payload)

    def _accept_reasoning(self, data: dict[str, Any]) -> None:
        now = self.clock()
        delta_events = max(1, int(data.get("delta_events") or 1))
        delta_characters = max(0, int(data.get("delta_characters") or 0))
        with self._lock:
            first = not self._reasoning_active
            if first:
                self._reasoning_active = True
                self._reasoning_started_at = now
                self._last_reasoning_pulse_at = now
                self.reasoning_events = 0
                self.reasoning_characters = 0
            self.reasoning_events += delta_events
            self.reasoning_characters += delta_characters
            pulse = not first and now - self._last_reasoning_pulse_at >= self.reasoning_pulse_seconds
            if pulse:
                self._last_reasoning_pulse_at = now
            payload = {
                "session_id": self.session_id,
                "delta_events": delta_events,
                "delta_characters": delta_characters,
                "total_events": self.reasoning_events,
                "total_characters": self.reasoning_characters,
                "elapsed_ms": max(0, round((now - self._reasoning_started_at) * 1000)),
            }
        if first:
            elapsed = self._mark_first("reasoning", "runner.first_reasoning")
            self.emit("runner.reasoning.started", {**payload, "first_reasoning_ms": elapsed})
        elif pulse:
            self.emit("runner.reasoning.activity", payload)

    def _mark_runtime_activity(self) -> None:
        with self._lock:
            if self.runtime_activity:
                return
            self.runtime_activity = True
        self._mark_first("activity", "runner.first_activity")

    def _mark_productive_phase(self, name: str) -> None:
        phases = {
            "agent.message.delta": ("text", "runner.first_text"),
            "tool.started": ("tool", "runner.first_tool"),
            "file.changed": ("output", "runner.first_output"),
        }
        phase = phases.get(name)
        if phase is None:
            return
        self.finish_reasoning("productive-output")
        elapsed = self._mark_first(*phase)
        with self._lock:
            first_productive = not self.productive_activity
            self.productive_activity = True
        if first_productive:
            self.emit(
                "runner.first_event",
                {"session_id": self.session_id, "elapsed_ms": elapsed},
            )

    def _mark_first(self, phase: str, event: str) -> int:
        if self.timing.marked(phase):
            return self.timing.mark(phase)
        elapsed = self.timing.mark(phase)
        self.emit(event, {"session_id": self.session_id, "elapsed_ms": elapsed})
        return elapsed
