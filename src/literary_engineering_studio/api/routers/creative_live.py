"""Project-level live creation read model and SSE endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...observability.creative_live.contracts import project_channel
from ...observability.creative_live.artifact_revisions import artifact_revisions
from ...observability.creative_live.projector import project_runtime_event
from ...observability.creative_live.snapshot import build_creative_live_snapshot
from ..common import call_handler, project_root as resolve_project_root
from ..streaming import sse_headers


@dataclass(frozen=True)
class CreativeLiveRouterDependencies:
    jobs: Any
    autopilot: Any
    live_events: Any
    sse: Callable[[str, dict[str, Any], int | str | None], str]


def build_creative_live_router(deps: CreativeLiveRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/creative-live")
    def creative_live(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: _snapshot(deps, root))

    @router.get("/creative-live/stream")
    def creative_live_stream(
        project_root: str,
        channels: str = "activity,artifact,review,transcript,usage,control",
        after: int = 0,
        max_events: int = 0,
    ):
        root = resolve_project_root(project_root)
        selected = {item.strip() for item in channels.split(",") if item.strip()}
        return _stream(deps, root, selected, max(0, after), max(0, max_events))

    @router.get("/creative-live/runs/{controller_id}/snapshot")
    def creative_run_snapshot(controller_id: str):
        def read():
            run = deps.jobs.read_autopilot_run(controller_id)
            return _snapshot(deps, resolve_project_root(str(run["project_root"])), run=run)

        return call_handler(read)

    @router.get("/creative-live/sessions/{session_id}")
    def creative_session(session_id: str, project_root: str):
        root = resolve_project_root(project_root)
        snapshot = _snapshot(deps, root)
        session = next(
            (item for item in snapshot["sessions"] if item.get("session_id") == session_id),
            None,
        )
        if session is None:
            raise ValueError("creative session was not found")
        return {"ok": True, "schema": "arcvellum/creative-live-session/v1", "session": session}

    @router.get("/creative-live/artifacts/{artifact_id}/revisions")
    def creative_artifact_revisions(artifact_id: str, project_root: str):
        root = resolve_project_root(project_root)
        revisions = artifact_revisions(root, _raw_events(deps, root)[0], artifact_id)
        return {
            "ok": True,
            "schema": "arcvellum/artifact-revisions/v1",
            "artifact_id": artifact_id,
            "revisions": [_revision_summary(item) for item in revisions],
        }

    @router.get("/creative-live/artifacts/{artifact_id}/revisions/{revision_id}")
    def creative_artifact_revision(artifact_id: str, revision_id: str, project_root: str):
        root = resolve_project_root(project_root)
        revision = next(
            (
                item
                for item in artifact_revisions(root, _raw_events(deps, root)[0], artifact_id)
                if item.get("revision_id") == revision_id
            ),
            None,
        )
        if revision is None:
            raise ValueError("artifact revision was not found")
        return {
            "ok": True,
            "schema": "arcvellum/artifact-revision/v1",
            "revision": revision,
        }

    return router


def _snapshot(
    deps: CreativeLiveRouterDependencies,
    root: Path,
    *,
    run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw, discovered_run = _raw_events(deps, root)
    current_run = run or discovered_run
    sessions = deps.jobs.list_agent_sessions(str(root), limit=40)
    return build_creative_live_snapshot(root, raw, sessions=sessions, run=current_run)


def _raw_events(
    deps: CreativeLiveRouterDependencies, root: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = deps.autopilot.status(root)
    current_run = status.get("run") if isinstance(status.get("run"), dict) else {}
    durable = (
        deps.jobs.autopilot_events_since(str(current_run.get("run_id") or ""), 0, limit=400)
        if current_run.get("run_id")
        else []
    )
    raw = [{**item, "source": "autopilot"} for item in durable]
    raw.extend(
        {**item, "source": "project-live"}
        for item in deps.live_events.wait_since(project_channel(root), 0, timeout=0)
    )
    return raw, current_run


def _revision_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "revision_id", "artifact_id", "event_id", "at", "identity",
            "digest", "characters", "finding_refs",
        )
    }


def _stream(
    deps: CreativeLiveRouterDependencies,
    root: Path,
    channels: set[str],
    after: int,
    max_events: int,
) -> StreamingResponse:
    channel = project_channel(root)

    def stream():
        live_cursor = after
        sent = 0
        snapshot = _snapshot(deps, root)
        yield deps.sse("creative.snapshot", snapshot, f"snapshot:{snapshot['revision']}")
        last_heartbeat = time.monotonic()
        while True:
            items = deps.live_events.wait_since(channel, live_cursor, timeout=0.8)
            for item in items:
                live_cursor = max(live_cursor, int(item.get("sequence") or 0))
                projected = project_runtime_event(item, root, source="project-live")
                if channels and projected["channel"] not in channels:
                    continue
                yield deps.sse("creative.event", projected, f"live:{live_cursor}")
                sent += 1
                if max_events and sent >= max_events:
                    return
            if time.monotonic() - last_heartbeat >= 10:
                yield ": creative live heartbeat\n\n"
                last_heartbeat = time.monotonic()

    return StreamingResponse(stream(), media_type="text/event-stream", headers=sse_headers())


__all__ = ["CreativeLiveRouterDependencies", "build_creative_live_router"]
