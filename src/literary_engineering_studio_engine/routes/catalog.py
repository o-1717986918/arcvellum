"""Route definition catalog for the formal task state machine.

The catalog connects a route's work-item selector, task builder, and gate
validator.  It deliberately receives these operations from the Registry so
this module stays free of route blueprint implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


WorkItemSelector = Callable[[Path, dict[str, object], Path | str | None], dict[str, object] | None]
TaskBuilder = Callable[[Path, str, dict[str, object]], dict[str, object]]
TaskValidator = Callable[[Path, dict[str, object]], tuple[list[str], list[str]]]


@dataclass(frozen=True)
class RouteDefinition:
    route: str
    ready_message: str
    select_work_item: WorkItemSelector
    build_task: TaskBuilder
    validate_task: TaskValidator


@dataclass(frozen=True)
class RouteCatalogCallbacks:
    scene_selector: WorkItemSelector
    builders: Mapping[str, TaskBuilder]
    validators: Mapping[str, TaskValidator]


ROUTE_READY_MESSAGES = {
    "scene-development": "no pending scene-development task found",
    "longform-planning": "longform-planning route is ready",
    "source-ingest": "source-ingest route has no pending imported source",
    "style-engineering": "style-engineering route has no pending style profile",
    "character-and-world-assets": "character-and-world-assets route has no pending candidate asset",
    "review-and-audit": "review-and-audit route is ready",
    "export-and-release": "export-and-release route has no pending chapter",
}


def route_definition(
    route: str,
    *,
    callbacks: RouteCatalogCallbacks,
    selectors: Mapping[str, WorkItemSelector],
) -> RouteDefinition:
    """Resolve a supported route without importing its blueprint module."""

    normalized = route.strip().lower().replace("_", "-")
    try:
        selector = callbacks.scene_selector if normalized == "scene-development" else selectors[normalized]
        return RouteDefinition(
            route=normalized,
            ready_message=ROUTE_READY_MESSAGES[normalized],
            select_work_item=selector,
            build_task=callbacks.builders[normalized],
            validate_task=callbacks.validators[normalized],
        )
    except KeyError as exc:
        raise ValueError(f"unsupported route: {route}") from exc
