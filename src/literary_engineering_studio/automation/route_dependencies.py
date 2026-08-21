"""Resolve bounded route dependencies without teaching the run loop literary rules."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .run_result_contracts import RouteCycle


DependencyProbe = Callable[[Path], bool]


def resolve_route_cycle(
    project: Path,
    route_order: tuple[str, ...],
    route_index: int,
    *,
    asset_probe: DependencyProbe,
    length_repair_probe: DependencyProbe,
    scene_probe: DependencyProbe,
    owner: str,
) -> RouteCycle:
    """Map one planned route to the only dependency route allowed by policy."""

    planned_route = route_order[route_index]
    if planned_route == "scene-development" and asset_probe(project):
        return RouteCycle(
            route_index=route_index,
            planned_route=planned_route,
            route="character-and-world-assets",
            dependency_route=True,
            owner=owner,
            dependency_kind="asset",
            resume_route_index=route_index,
        )
    if planned_route == "export-and-release" and length_repair_probe(project):
        resume_index = (
            route_order.index("review-and-audit")
            if "review-and-audit" in route_order
            else route_index
        )
        return RouteCycle(
            route_index=route_index,
            planned_route=planned_route,
            route="scene-development",
            dependency_route=True,
            owner=owner,
            dependency_kind="target-length-repair",
            resume_route_index=resume_index,
        )
    if planned_route == "export-and-release" and scene_probe(project):
        resume_index = (
            route_order.index("review-and-audit")
            if "review-and-audit" in route_order
            else route_index
        )
        return RouteCycle(
            route_index=route_index,
            planned_route=planned_route,
            route="scene-development",
            dependency_route=True,
            owner=owner,
            dependency_kind="scene-closure",
            resume_route_index=resume_index,
        )
    return RouteCycle(
        route_index=route_index,
        planned_route=planned_route,
        route=planned_route,
        dependency_route=False,
        owner=owner,
    )


def dependency_pending(
    project: Path,
    cycle: RouteCycle,
    *,
    asset_probe: DependencyProbe,
    length_repair_probe: DependencyProbe,
    scene_probe: DependencyProbe,
) -> bool:
    probes = {
        "asset": asset_probe,
        "target-length-repair": length_repair_probe,
        "scene-closure": scene_probe,
    }
    probe = probes.get(cycle.dependency_kind, asset_probe)
    return probe(project)


def dependency_label(cycle: RouteCycle) -> str:
    return {
        "target-length-repair": "全书目标长度返工",
        "scene-closure": "正式场景闭环",
    }.get(cycle.dependency_kind, "候选资产门禁")


__all__ = [
    "DependencyProbe",
    "dependency_label",
    "dependency_pending",
    "resolve_route_cycle",
]
