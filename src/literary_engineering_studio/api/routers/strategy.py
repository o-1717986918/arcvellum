"""Read-only creation strategy and typed plan event API routes (AO-8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Query

from ..common import project_root as resolve_project_root
from ..streaming import stream_typed_events


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
        project_root: str,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        root = resolve_project_root(project_root)
        return stream_typed_events(
            "plan-event",
            deps.list_typed_plan_events(root)[-limit:],
            interval_seconds=0.0,
            max_events=limit,
        )

    return router
