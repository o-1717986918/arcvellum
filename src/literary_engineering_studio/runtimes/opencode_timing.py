"""Content-free phase timings for one OpenCode execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any

from .base import RuntimeResult


_METADATA_KEYS = {
    "process_ready": "time_to_process_ready_ms",
    "session_created": "time_to_session_created_ms",
    "prompt_submitted": "time_to_prompt_submitted_ms",
    "reasoning": "time_to_first_reasoning_ms",
    "text": "time_to_first_text_ms",
    "tool": "time_to_first_tool_ms",
    "output": "time_to_first_output_ms",
}


@dataclass
class OpenCodeTiming:
    started_at: float = field(default_factory=time.monotonic)
    _marks: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def mark(self, phase: str) -> int:
        with self._lock:
            if phase not in self._marks:
                self._marks[phase] = round((time.monotonic() - self.started_at) * 1000)
            return self._marks[phase]

    def marked(self, phase: str) -> bool:
        with self._lock:
            return phase in self._marks

    def metadata(self, *, include_total: bool = True) -> dict[str, int]:
        with self._lock:
            result = {
                metadata_key: self._marks[phase]
                for phase, metadata_key in _METADATA_KEYS.items()
                if phase in self._marks
            }
        if include_total:
            result["total_ms"] = round((time.monotonic() - self.started_at) * 1000)
        return result


def attach_timing(result: RuntimeResult, timing: OpenCodeTiming) -> RuntimeResult:
    metadata: dict[str, Any] = {**(result.metadata or {}), **timing.metadata()}
    return RuntimeResult(
        result.runtime,
        result.status,
        result.returncode,
        result.command,
        result.output_path,
        result.message,
        metadata,
    )
