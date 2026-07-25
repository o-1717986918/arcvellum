"""SSE formatting and visible stream pacing for Studio API routers."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

try:
    from fastapi.responses import StreamingResponse
except ImportError:  # pragma: no cover - API creation fails before use
    StreamingResponse = None


def sse(event: str, data: dict[str, Any], event_id: int | str | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def visible_delta_chunks(value: str, target: int = 16, maximum: int = 28) -> list[str]:
    """Pace coarse provider deltas without inventing or rewriting answer text."""

    if len(value) <= maximum:
        return [value] if value else []
    chunks: list[str] = []
    cursor = 0
    punctuation = "，。！？；：、,.!?;:\n"
    while cursor < len(value):
        hard_end = min(len(value), cursor + maximum)
        preferred_end = min(len(value), cursor + target)
        end = hard_end
        for index in range(preferred_end, hard_end):
            if value[index] in punctuation:
                end = index + 1
                break
        chunks.append(value[cursor:end])
        cursor = end
    return chunks


def stream_read_model(event: str, function: Callable[[], dict[str, Any]], interval_seconds: float, max_events: int):
    """Emit read-model deltas and heartbeat comments using the existing SSE wire format."""

    interval = max(1.0, min(60.0, float(interval_seconds or 4.0)))
    limit = max(0, int(max_events or 0))

    def stream():
        sent = 0
        previous_digest = ""
        last_heartbeat = time.monotonic()
        while True:
            payload = function()
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            digest = read_model_revision(payload, serialized=serialized)
            if digest != previous_digest:
                yield f"event: {event}\n"
                yield "data: " + serialized + "\n\n"
                previous_digest = digest
                sent += 1
            elif time.monotonic() - last_heartbeat >= 15:
                yield f": {event} heartbeat\n\n"
                last_heartbeat = time.monotonic()
            if limit and sent >= limit:
                break
            time.sleep(interval)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def read_model_revision(payload: dict[str, Any], *, serialized: str | None = None) -> str:
    """Prefer an explicit semantic revision over volatile presentation fields."""

    explicit = str(payload.get("revision") or "").strip()
    if explicit:
        return f"revision:{explicit}"
    text = serialized if serialized is not None else json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
