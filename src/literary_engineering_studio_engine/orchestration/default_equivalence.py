"""Equivalence checks between a default plan and the fixed formal route."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .route_macros import default_route_macro


@dataclass(frozen=True)
class DefaultPlanEquivalence:
    compatible: bool
    issues: tuple[str, ...]


def check_default_plan_compatibility(
    *,
    route_macro_id: str,
    route_sequence: Iterable[str],
    supported_routes: Iterable[str],
) -> DefaultPlanEquivalence:
    macro = default_route_macro()
    sequence = tuple(str(item) for item in route_sequence)
    supported = frozenset(str(item) for item in supported_routes)
    issues: list[str] = []
    if route_macro_id != macro.macro_id:
        issues.append("default route macro id does not match the Engine macro")
    if sequence != macro.route_order:
        issues.append("default route sequence does not match the fixed Engine route order")
    unknown = tuple(route for route in sequence if route not in supported)
    if unknown:
        issues.append("default route sequence contains unsupported routes: " + ", ".join(unknown))
    return DefaultPlanEquivalence(compatible=not issues, issues=tuple(issues))
