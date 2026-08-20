"""Public-text streaming filter for advisor model output."""

from __future__ import annotations

from typing import Any, Callable

from .contracts import METADATA_MARKER


class PublicAnswerStream:
    def __init__(self, sink: Callable[[str, dict[str, Any]], None] | None):
        self.sink = sink
        self.buffer = ""
        self.hidden = False
        self.emitted = ""

    def feed(self, chunk: str) -> None:
        if not self.sink or self.hidden or not chunk:
            return
        self.buffer += chunk
        marker_at = self.buffer.find(METADATA_MARKER)
        if marker_at >= 0:
            self._emit(self.buffer[:marker_at])
            self.buffer = ""
            self.hidden = True
            return
        keep = marker_prefix_length(self.buffer, METADATA_MARKER)
        visible = self.buffer[:-keep] if keep else self.buffer
        self.buffer = self.buffer[-keep:] if keep else ""
        self._emit(visible)

    def finish(self, final_message: str) -> None:
        if not self.sink:
            return
        if not self.hidden:
            self._emit(self.buffer)
        missing = final_message[len(self.emitted):] if final_message.startswith(self.emitted) else ""
        self._emit(missing)
        self.sink("advisor.complete", {"message": final_message})

    def _emit(self, value: str) -> None:
        if value and self.sink:
            self.emitted += value
            self.sink("advisor.delta", {"text": value})


def marker_prefix_length(value: str, marker: str) -> int:
    maximum = min(len(value), len(marker) - 1)
    for size in range(maximum, 0, -1):
        if value.endswith(marker[:size]):
            return size
    return 0


__all__ = ["PublicAnswerStream", "marker_prefix_length"]
