"""Durable read-only Project Agent sessions and event streams."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..common import call_handler, project_root as resolve_project_root
from ..models import ProjectAgentSessionRequest, ProjectAgentTurnRequest


@dataclass(frozen=True)
class ProjectAgentRouterDependencies:
    service: Any
    jobs: Any
    sse: Callable[[str, dict[str, Any], int | str | None], str]
    numeric_resume_cursor: Callable[[int, str], int]
    stream_terminal: Callable[[str, str, int | str | None], str]


def build_project_agent_router(deps: ProjectAgentRouterDependencies) -> APIRouter:
    router = APIRouter(prefix="/project-agent")

    @router.get("/sessions")
    def list_sessions(project_root: str = "", limit: int = 30):
        root = resolve_project_root(project_root) if project_root.strip() else None
        return call_handler(
            lambda: {"ok": True, "items": deps.service.list_sessions(root, limit=limit)}
        )

    @router.post("/sessions")
    def create_session(payload: ProjectAgentSessionRequest):
        return call_handler(
            lambda: {
                "ok": True,
                **deps.service.create_session(
                    resolve_project_root(payload.project_root) if payload.project_root.strip() else None,
                    title=payload.title,
                ),
            }
        )

    @router.get("/sessions/{session_id}")
    def read_session(session_id: str):
        return call_handler(lambda: {"ok": True, **deps.service.read_session(session_id)})

    @router.post("/sessions/{session_id}/turns")
    def start_turn(session_id: str, payload: ProjectAgentTurnRequest):
        return call_handler(
            lambda: {
                "ok": True,
                **deps.service.start_turn(
                    session_id,
                    payload.message,
                    timeout=max(10, min(600, payload.timeout)),
                ),
            }
        )

    @router.get("/jobs/{job_id}")
    def read_turn(job_id: str):
        return call_handler(lambda: {"ok": True, **_project_agent_job(deps.jobs, job_id)})

    @router.post("/jobs/{job_id}/stop")
    def stop_turn(job_id: str):
        return call_handler(lambda: {"ok": True, **deps.service.cancel_turn(job_id)})

    @router.get("/jobs/{job_id}/events")
    def stream_turn_events(
        job_id: str,
        request: Request,
        after: int = 0,
        max_events: int = 0,
    ):
        call_handler(lambda: _project_agent_job(deps.jobs, job_id))
        cursor = deps.numeric_resume_cursor(after, request.headers.get("Last-Event-ID", ""))
        event_limit = max(0, min(5000, int(max_events or 0)))

        def stream():
            nonlocal cursor
            sent = 0
            last_heartbeat = time.monotonic()
            while True:
                events = deps.jobs.events_since(job_id, cursor, limit=200)
                for item in events:
                    cursor = int(item["sequence"])
                    yield deps.sse(
                        str(item["event"]),
                        {**item["data"], "at": item["at"], "job_id": job_id},
                        cursor,
                    )
                    sent += 1
                    if event_limit and sent >= event_limit:
                        yield deps.stream_terminal("project-agent", "event-limit", cursor)
                        return
                job = deps.jobs.read(job_id)
                if str(job.get("status") or "") not in {"queued", "running", "stopping"}:
                    if not events:
                        yield deps.stream_terminal("project-agent", str(job.get("status") or "complete"), cursor)
                        return
                if not events and time.monotonic() - last_heartbeat >= 15:
                    yield ": project-agent heartbeat\n\n"
                    last_heartbeat = time.monotonic()
                time.sleep(0.15)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


def _project_agent_job(jobs: Any, job_id: str) -> dict[str, Any]:
    job = jobs.read(job_id)
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    if request.get("kind") != "project-agent-turn":
        raise ValueError("job does not belong to the Project Agent")
    return job


__all__ = ["ProjectAgentRouterDependencies", "build_project_agent_router"]
