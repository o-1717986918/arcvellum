"""Narrative projection v2/v3 snapshots, node details, and delta streams."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..common import call_handler, project_root as resolve_project_root


@dataclass(frozen=True)
class NarrativeRouterDependencies:
    config: dict[str, Any]
    cached_read_model: Callable[..., dict[str, Any]]
    dashboard_snapshot: Callable[[Path], dict[str, Any]]
    narrative_evidence_snapshot: Callable[[Path], dict[str, Any]]
    library_snapshot: Callable[[Path], dict[str, Any]]
    build_projection: Callable[..., dict[str, Any]]
    projection_delta: Callable[[dict[str, Any] | None, dict[str, Any]], dict[str, Any]]
    projection_motion_events: Callable[..., list[dict[str, Any]]]
    build_projection_v3: Callable[..., dict[str, Any]]
    build_node_detail_v3: Callable[..., dict[str, Any]]
    build_projection_v4: Callable[..., dict[str, Any]]
    build_node_detail_v4: Callable[..., dict[str, Any]]
    spatial_projection_delta: Callable[[dict[str, Any] | None, dict[str, Any]], dict[str, Any]]
    spatial_projection_motion_events: Callable[..., list[dict[str, Any]]]
    spatial_projection_patch: Callable[..., dict[str, Any]]
    v2_stream_state: dict[str, dict[str, Any]]
    v3_stream_state: dict[str, dict[str, Any]]
    v4_stream_state: dict[str, dict[str, Any]]
    stream_lock: Lock
    sse: Callable[[str, dict[str, Any], int | str | None], str]


def _projection(deps: NarrativeRouterDependencies, root: Path, level: str, focus: str) -> dict[str, Any]:
    return deps.cached_read_model(
        f"narrative:{root}:{level}:{focus}",
        root,
        lambda: deps.build_projection(
            deps.config,
            root,
            level=level,
            focus=focus,
            dashboard_payload=deps.dashboard_snapshot(root),
            library_payload=deps.narrative_evidence_snapshot(root),
        ),
    )


def _projection_v3(deps: NarrativeRouterDependencies, root: Path, level: str, focus: str, grammar: str) -> dict[str, Any]:
    return deps.cached_read_model(
        f"narrative-v3:{root}:{level}:{focus}:{grammar}",
        root,
        lambda: deps.build_projection_v3(
            deps.config,
            root,
            level=level,
            focus=focus,
            grammar=grammar,
            dashboard_payload=deps.dashboard_snapshot(root),
            library_payload=deps.narrative_evidence_snapshot(root),
        ),
    )


def _projection_v4(deps: NarrativeRouterDependencies, root: Path, level: str, focus: str, grammar: str) -> dict[str, Any]:
    return deps.cached_read_model(
        f"narrative-v4:{root}:{level}:{focus}:{grammar}",
        root,
        lambda: deps.build_projection_v4(
            deps.config,
            root,
            level=level,
            focus=focus,
            grammar=grammar,
            dashboard_payload=deps.dashboard_snapshot(root),
            library_payload=deps.library_snapshot(root),
        ),
    )


def _v3_transition(
    deps: NarrativeRouterDependencies,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    sequence: int,
) -> tuple[str, dict[str, Any]]:
    return _spatial_transition(deps, previous, current, sequence, version=3)


def _v4_transition(
    deps: NarrativeRouterDependencies,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    sequence: int,
) -> tuple[str, dict[str, Any]]:
    return _spatial_transition(deps, previous, current, sequence, version=4)


def _spatial_transition(
    deps: NarrativeRouterDependencies,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    sequence: int,
    *,
    version: int,
) -> tuple[str, dict[str, Any]]:
    delta = deps.spatial_projection_delta(previous, current)
    motion_events = deps.spatial_projection_motion_events(previous, current, delta)
    if previous is None:
        payload = dict(current)
        payload.update({"sequence": sequence, "delta": delta, "motion_events": motion_events})
        return f"narrative.v{version}.projection", payload
    return (
        f"narrative.v{version}.patch",
        deps.spatial_projection_patch(
            previous,
            current,
            sequence=sequence,
            delta=delta,
            motion_events=motion_events,
        ),
    )


def _v3_streaming_response(
    deps: NarrativeRouterDependencies,
    root: Path,
    level: str,
    focus: str,
    grammar: str,
    interval: float,
    limit: int,
) -> StreamingResponse:
    return _spatial_streaming_response(
        deps,
        root,
        level,
        focus,
        grammar,
        interval,
        limit,
        version=3,
    )


def _v4_streaming_response(
    deps: NarrativeRouterDependencies,
    root: Path,
    level: str,
    focus: str,
    grammar: str,
    interval: float,
    limit: int,
) -> StreamingResponse:
    return _spatial_streaming_response(
        deps,
        root,
        level,
        focus,
        grammar,
        interval,
        limit,
        version=4,
    )


def _spatial_streaming_response(
    deps: NarrativeRouterDependencies,
    root: Path,
    level: str,
    focus: str,
    grammar: str,
    interval: float,
    limit: int,
    *,
    version: int,
) -> StreamingResponse:
    projection_builder = _projection_v4 if version == 4 else _projection_v3
    stream_state = deps.v4_stream_state if version == 4 else deps.v3_stream_state

    def stream():
        sent = 0
        stream_key = f"{root}|{level}|{focus}|{grammar}"
        while True:
            projection = projection_builder(deps, root, level, focus, grammar)
            revision = str(projection.get("revision") or "")
            event_name = ""
            event_payload: dict[str, Any] | None = None
            with deps.stream_lock:
                state = stream_state.get(stream_key, {})
                previous = state.get("projection") if isinstance(state.get("projection"), dict) else None
                previous_revision = str((previous or {}).get("revision") or "")
                if revision != previous_revision:
                    sequence = int(state.get("sequence") or 0) + 1
                    event_name, event_payload = _spatial_transition(deps, previous, projection, sequence, version=version)
                    stream_state[stream_key] = {
                        "sequence": sequence,
                        "projection": projection,
                    }
                else:
                    sequence = int(state.get("sequence") or 0)
            if event_payload is not None:
                yield deps.sse(event_name, event_payload, sequence)
                sent += 1
                if limit and sent >= limit:
                    break
            else:
                yield f": narrative v{version} heartbeat\n\n"
            time.sleep(interval)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _v2_streaming_response(
    deps: NarrativeRouterDependencies,
    root: Path,
    level: str,
    focus: str,
    interval: float,
    limit: int,
) -> StreamingResponse:
    def stream():
        sent = 0
        stream_key = f"{root}|{level}|{focus}"
        while True:
            projection = _projection(deps, root, level, focus)
            revision = str(projection.get("revision") or "")
            with deps.stream_lock:
                state = deps.v2_stream_state.get(stream_key, {})
                previous = state.get("projection") if isinstance(state.get("projection"), dict) else None
                previous_revision = str((previous or {}).get("revision") or "")
                delta = deps.projection_delta(previous, projection) if revision != previous_revision else None
                sequence = int(state.get("sequence") or 0) + (1 if delta is not None else 0)
                if delta is not None:
                    projection["sequence"] = sequence
                    projection["delta"] = delta
                    projection["motion_events"] = deps.projection_motion_events(previous, projection, delta)
                    deps.v2_stream_state[stream_key] = {"sequence": sequence, "projection": projection}
            if delta is not None:
                yield deps.sse("narrative.projection", projection, sequence)
                sent += 1
                if limit and sent >= limit:
                    break
            else:
                yield ": narrative heartbeat\n\n"
            time.sleep(interval)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _register_v2_routes(router: APIRouter, deps: NarrativeRouterDependencies) -> None:
    @router.get("/narrative/projection")
    def narrative_projection(project_root: str, level: str = "book", focus: str = ""):
        root = resolve_project_root(project_root)
        return call_handler(lambda: _projection(deps, root, level, focus))

    @router.get("/narrative/stream")
    def narrative_stream(project_root: str, level: str = "book", focus: str = "", interval_seconds: float = 6.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 6.0)))
        limit = max(0, int(max_events or 0))
        return _v2_streaming_response(deps, root, level, focus, interval, limit)


def _register_v3_routes(router: APIRouter, deps: NarrativeRouterDependencies) -> None:
    @router.get("/narrative/projection/v3")
    def narrative_projection_v3(project_root: str, level: str = "book", focus: str = "", grammar: str = "auto"):
        root = resolve_project_root(project_root)
        return call_handler(lambda: _projection_v3(deps, root, level, focus, grammar))

    @router.get("/narrative/projection/v3/nodes/{node_id}")
    def narrative_projection_v3_node(node_id: str, project_root: str, level: str = "book", focus: str = "", grammar: str = "auto"):
        root = resolve_project_root(project_root)
        try:
            return call_handler(
                lambda: deps.build_node_detail_v3(
                    deps.config,
                    root,
                    node_id,
                    level=level,
                    focus=focus,
                    grammar=grammar,
                    dashboard_payload=deps.dashboard_snapshot(root),
                    library_payload=deps.narrative_evidence_snapshot(root),
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="未找到这个叙事节点。") from exc

    @router.get("/narrative/stream/v3")
    def narrative_stream_v3(project_root: str, level: str = "book", focus: str = "", grammar: str = "auto", interval_seconds: float = 6.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 6.0)))
        limit = max(0, int(max_events or 0))
        return _v3_streaming_response(deps, root, level, focus, grammar, interval, limit)


def _register_v4_routes(router: APIRouter, deps: NarrativeRouterDependencies) -> None:
    @router.get("/narrative/projection/v4")
    def narrative_projection_v4(project_root: str, level: str = "book", focus: str = "", grammar: str = "auto"):
        root = resolve_project_root(project_root)
        return call_handler(lambda: _projection_v4(deps, root, level, focus, grammar))

    @router.get("/narrative/projection/v4/nodes/{node_id}")
    def narrative_projection_v4_node(node_id: str, project_root: str, level: str = "book", focus: str = "", grammar: str = "auto"):
        root = resolve_project_root(project_root)
        try:
            return call_handler(
                lambda: deps.build_node_detail_v4(
                    deps.config,
                    root,
                    node_id,
                    level=level,
                    focus=focus,
                    grammar=grammar,
                    dashboard_payload=deps.dashboard_snapshot(root),
                    library_payload=deps.library_snapshot(root),
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="未找到这个创作节点。") from exc

    @router.get("/narrative/stream/v4")
    def narrative_stream_v4(project_root: str, level: str = "book", focus: str = "", grammar: str = "auto", interval_seconds: float = 6.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 6.0)))
        limit = max(0, int(max_events or 0))
        return _v4_streaming_response(deps, root, level, focus, grammar, interval, limit)


def build_narrative_router(deps: NarrativeRouterDependencies) -> APIRouter:
    """Build projection endpoints without letting the client infer formal story state."""

    router = APIRouter()
    _register_v2_routes(router, deps)
    _register_v3_routes(router, deps)
    _register_v4_routes(router, deps)
    return router
