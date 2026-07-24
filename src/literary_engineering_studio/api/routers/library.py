"""Project library, live workspace, and formal-manuscript reader routes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..common import call_handler, project_root as resolve_project_root
from ..models import ReaderBookmarkRequest, ReaderPositionRequest


@dataclass(frozen=True)
class LibraryRouterDependencies:
    jobs: Any
    cached_read_model: Callable[..., dict[str, Any]]
    library_snapshot: Callable[[Path], dict[str, Any]]
    progress_snapshot: Callable[[Path], dict[str, Any]]
    workspace_snapshot: Callable[[Path], dict[str, Any]]
    reader_snapshot: Callable[[Path], dict[str, Any]]
    build_reader_manifest: Callable[[Path], dict[str, Any]]
    public_reader_manifest: Callable[[dict[str, Any]], dict[str, Any]]
    read_reader_unit: Callable[[Path, str], dict[str, Any]]
    search_reader: Callable[[Path, str], dict[str, Any]]
    stream_read_model: Callable[[str, Callable[[], dict[str, Any]], float, int], Any]
    sse: Callable[[str, dict[str, Any], int | str | None], str]


def build_library_router(deps: LibraryRouterDependencies) -> APIRouter:
    """Build only read-model/reader endpoints; formal mutations remain in workflow routes."""

    router = APIRouter()

    @router.get("/project/library")
    def project_library(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.library_snapshot(root))

    @router.get("/project/library/stream")
    def project_library_stream(project_root: str, interval_seconds: float = 6.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model("library", lambda: deps.library_snapshot(root), interval_seconds, max_events)

    @router.get("/project/progress")
    def project_progress(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.progress_snapshot(root))

    @router.get("/project/progress/stream")
    def project_progress_stream(project_root: str, interval_seconds: float = 5.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model("project.progress", lambda: deps.progress_snapshot(root), interval_seconds, max_events)

    @router.get("/project/workspace/stream")
    def project_workspace_stream(project_root: str, interval_seconds: float = 2.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model("workspace.snapshot", lambda: deps.workspace_snapshot(root), interval_seconds, max_events)

    @router.get("/project/workspace")
    def project_workspace(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.workspace_snapshot(root))

    @router.get("/reader/manifest")
    def reader_manifest(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.reader_snapshot(root))

    @router.get("/reader/units/{unit_id}")
    def reader_unit(unit_id: str, project_root: str):
        return call_handler(lambda: deps.read_reader_unit(resolve_project_root(project_root), unit_id))

    @router.get("/reader/search")
    def reader_search(project_root: str, q: str, limit: int = 40):
        return call_handler(lambda: deps.search_reader(resolve_project_root(project_root), q, limit=limit))

    @router.get("/reader/state")
    def reader_state(project_root: str):
        root = resolve_project_root(project_root)
        return {"ok": True, "schema": "arcvellum/reader-state/v1", **deps.jobs.reader_state(str(root))}

    @router.put("/reader/position")
    def reader_position(payload: ReaderPositionRequest):
        root = resolve_project_root(payload.project_root)
        return {
            "ok": True,
            "schema": "arcvellum/reader-state/v1",
            **deps.jobs.save_reader_position(str(root), payload.unit_id, payload.scroll_ratio),
        }

    @router.put("/reader/bookmark")
    def reader_bookmark(payload: ReaderBookmarkRequest):
        root = resolve_project_root(payload.project_root)
        return {
            "ok": True,
            "schema": "arcvellum/reader-state/v1",
            **deps.jobs.set_reader_bookmark(str(root), payload.unit_id, payload.enabled),
        }

    @router.get("/reader/stream")
    def reader_stream(project_root: str, interval_seconds: float = 4.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(1.0, min(60.0, float(interval_seconds or 4.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            previous: dict[str, Any] | None = None
            while True:
                manifest = deps.cached_read_model(
                    f"reader:{root}", root, lambda: deps.public_reader_manifest(deps.build_reader_manifest(root))
                )
                revision = str(manifest.get("project_revision") or "")
                if previous is None or revision != str(previous.get("project_revision") or ""):
                    previous_ids = {str(item.get("unit_id")) for item in (previous or {}).get("units", []) if isinstance(item, dict)}
                    current_ids = {str(item.get("unit_id")) for item in manifest.get("units", []) if isinstance(item, dict)}
                    payload = {
                        **manifest,
                        "delta": {"added": sorted(current_ids - previous_ids), "removed": sorted(previous_ids - current_ids), "initial": previous is None},
                    }
                    yield deps.sse("reader.manifest", payload, None)
                    previous = manifest
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": reader heartbeat\n\n"
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
