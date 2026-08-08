"""Read-only creation strategy and typed plan event API routes (AO-8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Query, Request

from ..common import project_root as resolve_project_root
from ..streaming import stream_typed_event_tail


@dataclass(frozen=True)
class StrategyRouterDependencies:
    load_strategy_projection: Callable[[Path], dict[str, Any]]
    list_typed_plan_events: Callable[[Path], list[dict[str, Any]]]


def build_strategy_router(deps: StrategyRouterDependencies) -> APIRouter:
    """Build read-only strategy endpoints; writes stay on the formal CLI."""
    router = APIRouter()

    @router.get("/project/strategy")
    def project_strategy(project_root: str):
        root = resolve_project_root(project_root)
        return {
            "ok": True,
            "strategy": deps.load_strategy_projection(root),
        }

    @router.get("/project/strategy/events")
    def project_strategy_events(
        request: Request,
        project_root: str,
        limit: int = Query(default=50, ge=1, le=200),
        after_event_id: str = "",
        follow: bool = False,
        interval_seconds: float = Query(default=1.0, ge=0.1, le=30.0),
        max_events: int = Query(default=0, ge=0, le=1000),
    ):
        root = resolve_project_root(project_root)
        cursor = str(
            request.headers.get("Last-Event-ID") or after_event_id or ""
        )
        return stream_typed_event_tail(
            "plan-event",
            lambda: deps.list_typed_plan_events(root)[-limit:],
            after_event_id=cursor,
            follow=follow,
            interval_seconds=interval_seconds,
            max_events=max_events,
        )

    return router
