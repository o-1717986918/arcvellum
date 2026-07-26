"""Deterministic route macros that preserve the fixed formal workflow."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ROUTE_ORDER = (
    "source-ingest",
    "longform-planning",
    "style-engineering",
    "character-and-world-assets",
    "scene-development",
    "review-and-audit",
    "export-and-release",
)


@dataclass(frozen=True)
class RouteMacro:
    macro_id: str
    route_order: tuple[str, ...]
    description: str


def default_route_macro() -> RouteMacro:
    return RouteMacro(
        macro_id="fixed-formal-route.v1",
        route_order=DEFAULT_ROUTE_ORDER,
        description="Behavior-preserving projection of the current formal route order.",
    )
