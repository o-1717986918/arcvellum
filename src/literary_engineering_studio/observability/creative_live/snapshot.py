"""Build a reconnectable Creative Live read model from durable and live events."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .artifact_projection import reduce_artifacts
from .contracts import project_id
from .projector import project_runtime_event
from .review_projection import review_events
from .review_artifacts import apply_review_identities, project_review_artifacts
from .transcript_projection import reduce_sessions


SNAPSHOT_SCHEMA = "arcvellum/creative-live-snapshot/v1"


def build_creative_live_snapshot(
    project_root: str | Path,
    raw_events: Iterable[dict[str, Any]],
    *,
    sessions: list[dict[str, Any]] | None = None,
    run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    projected = _unique_events(
        project_runtime_event(item, project_root, source=str(item.get("source") or "runtime"))
        for item in raw_events
    )
    visible = [item for item in projected if item.get("visibility") != "restricted"]
    visible.extend(project_review_artifacts(project_root, visible))
    visible = _unique_events(visible)
    projected_reviews = [item for item in visible if item.get("channel") == "review"]
    artifacts = apply_review_identities(reduce_artifacts(visible), projected_reviews)
    session_projection = reduce_sessions(visible, sessions)
    current_run = run or {}
    revision_source = {
        "event_ids": [item["event_id"] for item in visible],
        "artifact_states": [
            (item.get("artifact_id"), item.get("identity"), item.get("digest"), item.get("characters"))
            for item in artifacts
        ],
        "run": {
            key: current_run.get(key)
            for key in ("run_id", "status", "current_task_id", "current_route", "updated_at")
        },
    }
    revision = hashlib.sha256(
        json.dumps(revision_source, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return {
        "ok": True,
        "schema": SNAPSHOT_SCHEMA,
        "project_id": project_id(project_root),
        "revision": revision,
        "status": _status(current_run, session_projection),
        "controller": _controller(current_run),
        "active_task": _active_task(current_run, visible),
        "artifacts": artifacts,
        "sessions": session_projection,
        "activity": _activity(visible),
        "reviews": review_events(visible),
        "usage": _usage(visible),
        "events": visible[-240:],
        "cursor": max((int(item.get("sequence") or 0) for item in visible), default=0),
    }


def _unique_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in events:
        event_id = str(item.get("event_id") or "")
        if not event_id:
            continue
        if event_id not in values:
            order.append(event_id)
        values[event_id] = item
    return [values[event_id] for event_id in order]


def _status(run: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    if str(run.get("status") or "") == "running":
        return "active"
    if any(str(item.get("status") or "") == "running" for item in sessions):
        return "active"
    if str(run.get("status") or "") in {"blocked", "failed"}:
        return "blocked"
    if str(run.get("status") or "") == "paused":
        return "paused"
    return "idle"


def _controller(run: dict[str, Any]) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        key: run.get(key)
        for key in (
            "run_id", "status", "runtime", "current_route", "current_task_id",
            "tasks_completed", "failures", "estimated_cost", "updated_at",
        )
    }


def _active_task(run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    task_id = str(run.get("current_task_id") or "")
    route = str(run.get("current_route") or "")
    latest = next((item for item in reversed(events) if item.get("task_id") or item.get("route")), None)
    if not task_id and latest:
        task_id = str(latest.get("task_id") or "")
        route = str(latest.get("route") or "")
    if not task_id and not route:
        return None
    return {
        "task_id": task_id,
        "route": route,
        "title": _route_title(route),
        "last_event": latest.get("event") if latest else "",
        "message": (latest.get("data") or {}).get("message") if latest else "",
    }


def _activity(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": item.get("event_id"),
            "event": item.get("event"),
            "channel": item.get("channel"),
            "at": item.get("at"),
            "task_id": item.get("task_id"),
            "route": item.get("route"),
            "title": (item.get("data") or {}).get("title"),
            "message": (item.get("data") or {}).get("message"),
        }
        for item in events
        if item.get("channel") in {"activity", "control", "artifact", "review"}
    ][-120:]


def _usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = 0
    cost = 0.0
    requests = 0
    for item in events:
        if item.get("channel") != "usage":
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        total_tokens += int(usage.get("total_tokens") or 0)
        cost += float(data.get("cost_usd") or 0)
        requests += 1
    return {"total_tokens": total_tokens, "cost_usd": round(cost, 8), "updates": requests}


def _route_title(route: str) -> str:
    return {
        "source-ingest": "理解创作方向",
        "longform-planning": "规划长篇结构",
        "style-engineering": "建立文风",
        "character-and-world-assets": "完善人物与世界",
        "scene-development": "创作正文",
        "review-and-audit": "审查与修订",
        "export-and-release": "汇编交付",
    }.get(route, "推进作品")


__all__ = ["SNAPSHOT_SCHEMA", "build_creative_live_snapshot"]
