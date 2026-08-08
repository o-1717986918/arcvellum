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


def sse_headers() -> dict[str, str]:
    return {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def numeric_resume_cursor(after: int, last_event_id: str) -> int:
    """Resolve a durable numeric cursor; malformed headers never rewind it."""

    query_cursor = max(0, int(after or 0))
    try:
        header_cursor = int(str(last_event_id or "0"))
    except ValueError:
        return query_cursor
    return max(query_cursor, header_cursor)


def stream_terminal(source: str, status: str, cursor: int | str | None) -> str:
    return sse(
        "stream.terminal",
        {"source": source, "status": status, "cursor": cursor},
    )


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
        headers=sse_headers(),
    )


def stream_typed_events(
    event: str,
    events: list[dict[str, Any]],
    *,
    interval_seconds: float = 0.0,
    max_events: int = 0,
):
    """Emit typed plan events over SSE with stable event ids and pacing."""
    interval = max(0.0, min(60.0, float(interval_seconds or 0.0)))
    limit = max(0, int(max_events or 0))

    def stream():
        sent = 0
        for item in events:
            yield sse(
                event,
                item,
                event_id=str(item.get("event_id") or sent + 1),
            )
            sent += 1
            if limit and sent >= limit:
                break
            if interval:
                time.sleep(interval)
        yield f": {event} stream complete\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers=sse_headers(),
    )


def stream_typed_event_tail(
    event: str,
    load_events: Callable[[], list[dict[str, Any]]],
    *,
    after_event_id: str = "",
    follow: bool = False,
    interval_seconds: float = 1.0,
    max_events: int = 0,
):
    """Tail a bounded typed audit list with explicit reset and close semantics."""

    interval = max(0.1, min(30.0, float(interval_seconds or 1.0)))
    limit = max(0, int(max_events or 0))

    def stream():
        cursor = str(after_event_id or "")
        sent = 0
        first = True
        last_heartbeat = time.monotonic()
        while True:
            events = load_events()
            start, reset = _tail_start(events, cursor, first=first)
            if reset:
                yield sse(
                    "stream.reset",
                    {"source": event, "reason": "cursor-not-found", "cursor": cursor},
                )
            first = False
            for item in events[start:]:
                event_id = str(item.get("event_id") or "")
                if not event_id:
                    continue
                cursor = event_id
                yield sse(event, item, event_id=event_id)
                sent += 1
                if limit and sent >= limit:
                    yield stream_terminal(event, "max-events", cursor)
                    return
            if not follow:
                yield f": {event} stream complete\n\n"
                yield stream_terminal(event, "replay-complete", cursor)
                return
            if time.monotonic() - last_heartbeat >= 15:
                yield f": {event} heartbeat\n\n"
                last_heartbeat = time.monotonic()
            time.sleep(interval)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers=sse_headers(),
    )


def _tail_start(
    events: list[dict[str, Any]],
    cursor: str,
    *,
    first: bool,
) -> tuple[int, bool]:
    if not cursor:
        return 0, False
    for index, item in enumerate(events):
        if str(item.get("event_id") or "") == cursor:
            return index + 1, False
    return 0, first


def read_model_revision(payload: dict[str, Any], *, serialized: str | None = None) -> str:
    """Prefer an explicit semantic revision over volatile presentation fields."""

    explicit = str(payload.get("revision") or "").strip()
    if explicit:
        return f"revision:{explicit}"
    text = serialized if serialized is not None else json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
