"""Observe OpenCode events without retaining prompts or reasoning content."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
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
    public_activity: bool = False
    usage_summary: dict[str, Any] = field(default_factory=dict)
    tool_states: dict[str, str] = field(default_factory=dict)

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
        if name == "runner.reasoning.activity":
            self._mark_first("reasoning", "runner.first_reasoning")
            return
        self._mark_public_phase(name)
        if name == "file.changed":
            self._mark_first("output", "runner.first_output")
        if name == "usage.updated":
            merge_usage_summary(self.usage_summary, data)
        self.emit(name, normalize_model_warning(name, data, self.errors))

    def _mark_public_phase(self, name: str) -> None:
        phases = {
            "agent.message.delta": ("text", "runner.first_text"),
            "tool.started": ("tool", "runner.first_tool"),
        }
        phase = phases.get(name)
        if phase is None:
            return
        elapsed = self._mark_first(*phase)
        if not self.public_activity:
            self.public_activity = True
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
