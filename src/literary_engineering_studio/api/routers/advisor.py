"""Advisor sessions, personas, inbox, and streaming conversation routes."""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..common import call_handler, project_root as resolve_project_root
from ..models import (
    AdvisorCustomPersonaRequest,
    AdvisorInboxReadRequest,
    AdvisorInboxSettingsRequest,
    AdvisorPersonaSelectionRequest,
    AdvisorQuestionRequest,
    AdvisorSessionRequest,
)


@dataclass(frozen=True)
class AdvisorRouterDependencies:
    config: dict[str, Any]
    jobs: Any
    advisor: Any
    dashboard_snapshot: Callable[[Path], dict[str, Any]]
    persona_catalog: Callable[[Path, Path], dict[str, Any]]
    select_persona: Callable[[Path, Path, str], dict[str, Any]]
    save_custom_persona: Callable[..., dict[str, Any]]
    refresh_advisor_inbox: Callable[..., dict[str, Any]]
    save_inbox_settings: Callable[[Path, Path, dict[str, Any]], dict[str, Any]]
    sse: Callable[[str, dict[str, Any], int | str | None], str]
    visible_delta_chunks: Callable[[str], list[str]]
    friendly_error: Callable[[Exception], str]


def build_advisor_router(deps: AdvisorRouterDependencies) -> APIRouter:
    """Build advisor routes while keeping its project access read-only by contract."""

    router = APIRouter()

    @router.get("/advisor/sessions")
    def advisor_sessions(project_root: str):
        return call_handler(lambda: {"ok": True, "items": deps.advisor.list_sessions(resolve_project_root(project_root))})

    @router.get("/advisor/personas")
    def advisor_personas(project_root: str):
        return call_handler(lambda: deps.persona_catalog(deps.advisor._data_root(), resolve_project_root(project_root)))

    @router.put("/advisor/personas/selection")
    def advisor_persona_selection(payload: AdvisorPersonaSelectionRequest):
        return call_handler(
            lambda: deps.select_persona(
                deps.advisor._data_root(), resolve_project_root(payload.project_root), payload.persona_id
            )
        )

    @router.put("/advisor/personas/custom")
    def advisor_persona_custom(payload: AdvisorCustomPersonaRequest):
        return call_handler(
            lambda: deps.save_custom_persona(
                deps.advisor._data_root(),
                name=payload.name,
                tagline=payload.tagline,
                prompt=payload.prompt,
                persona_id=payload.persona_id,
            )
        )

    @router.get("/advisor/inbox")
    def advisor_inbox(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(
            lambda: deps.refresh_advisor_inbox(
                deps.config,
                deps.jobs,
                root,
                dashboard_payload=deps.dashboard_snapshot(root),
            )
        )

    @router.patch("/advisor/inbox/{item_id}")
    def advisor_inbox_read(item_id: str, payload: AdvisorInboxReadRequest):
        return call_handler(lambda: {"ok": True, "item": deps.jobs.mark_advisor_inbox_read(item_id, read=payload.read)})

    @router.put("/advisor/inbox/settings")
    def advisor_inbox_settings(payload: AdvisorInboxSettingsRequest):
        return call_handler(
            lambda: {
                "ok": True,
                "settings": deps.save_inbox_settings(
                    deps.advisor._data_root(),
                    resolve_project_root(payload.project_root),
                    {"mode": payload.mode, "quiet_start": payload.quiet_start, "quiet_end": payload.quiet_end},
                ),
            }
        )

    @router.get("/advisor/inbox/stream")
    def advisor_inbox_stream(project_root: str, interval_seconds: float = 8.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 8.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            previous = ""
            sent = 0
            while True:
                snapshot = deps.refresh_advisor_inbox(
                    deps.config,
                    deps.jobs,
                    root,
                    dashboard_payload=deps.dashboard_snapshot(root),
                )
                signature = json.dumps(snapshot.get("items", []), ensure_ascii=False, sort_keys=True)
                if signature != previous:
                    yield deps.sse("advisor.inbox", snapshot, None)
                    previous = signature
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": advisor inbox heartbeat\n\n"
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.post("/advisor/sessions")
    def advisor_session_create(payload: AdvisorSessionRequest):
        return call_handler(lambda: {"ok": True, **deps.advisor.create_session(resolve_project_root(payload.project_root), title=payload.title)})

    @router.get("/advisor/sessions/{session_id}")
    def advisor_session_read(session_id: str):
        return call_handler(lambda: {"ok": True, **deps.jobs.read_advisor_session(session_id)})

    @router.post("/advisor/sessions/{session_id}/ask")
    def advisor_session_ask(session_id: str, payload: AdvisorQuestionRequest):
        return call_handler(
            lambda: {
                "ok": True,
                "session_id": session_id,
                "answer": deps.advisor.ask(
                    session_id,
                    payload.question,
                    timeout=max(10, min(600, payload.timeout)),
                    context=payload.context or {},
                ),
            }
        )

    @router.post("/advisor/sessions/{session_id}/ask/stream")
    def advisor_session_ask_stream(session_id: str, payload: AdvisorQuestionRequest):
        events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()

        def emit(event: str, data: dict[str, Any]) -> None:
            events.put((event, data))

        def run() -> None:
            try:
                result = deps.advisor.ask(
                    session_id,
                    payload.question,
                    timeout=max(10, min(600, payload.timeout)),
                    context=payload.context or {},
                    event_sink=emit,
                )
                events.put(("advisor.result", {"answer": result}))
            except Exception as exc:
                events.put(("advisor.error", {"message": deps.friendly_error(exc)}))
            finally:
                events.put(("advisor.closed", {}))

        threading.Thread(target=run, name=f"arcvellum-advisor-{session_id}", daemon=True).start()

        def stream():
            yield deps.sse("advisor.opened", {"session_id": session_id}, None)
            while True:
                try:
                    event, data = events.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if event == "advisor.delta":
                    chunks = deps.visible_delta_chunks(str(data.get("text") or ""))
                    for chunk in chunks:
                        yield deps.sse(event, {**data, "text": chunk}, None)
                        if len(chunks) > 1:
                            time.sleep(0.014)
                else:
                    yield deps.sse(event, data, None)
                if event == "advisor.closed":
                    break

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
