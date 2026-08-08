"""Chapter-level window policy projection for AO-5 (W6-6C).

The chapter window and risk profiles are projected onto an existing plan
candidate before the deterministic AO-2 pipeline runs.  This module never
creates tasks, never writes project facts, and never activates a plan.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping, Sequence

from .risk import SceneRiskLevel, SceneRiskProfile
from .rolling_horizon import RollingHorizonWindow

_DEPTH_BY_LEVEL = {
    SceneRiskLevel.COMPACT: "light",
    SceneRiskLevel.STANDARD: "targeted",
    SceneRiskLevel.DEEP: "full",
}
_BRANCH_BY_LEVEL = {
    SceneRiskLevel.COMPACT: 2,
    SceneRiskLevel.STANDARD: 3,
    SceneRiskLevel.DEEP: 5,
}
_DEPTH_RANK = {"light": 0, "targeted": 1, "full": 2}
_ROLEPLAY_KIND = "roleplay_simulation"
_BRANCH_KIND = "scene_branch_simulation"


@dataclass(frozen=True)
class ChapterWindowPolicy:
    chapter_id: str
    active_scene_id: str
    deep_scene_ids: tuple[str, ...]
    horizon_size: int
    base_project_revision: str
    scene_risk_levels: tuple[tuple[str, str], ...]
    branch_count: int
    rebase_after: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "chapter_id": self.chapter_id,
            "active_scene_id": self.active_scene_id,
            "deep_scene_ids": list(self.deep_scene_ids),
            "horizon_size": self.horizon_size,
            "base_project_revision": self.base_project_revision,
            "scene_risk_levels": [
                {"scene_id": scene_id, "level": level}
                for scene_id, level in self.scene_risk_levels
            ],
            "branch_count": self.branch_count,
            "rebase_after": list(self.rebase_after),
        }


def chapter_scene_minimums(
    policy: ChapterWindowPolicy,
    scene_id: str,
) -> tuple[str, int]:
    """Return the machine-owned minimum RP depth and branch count."""

    level_by_scene = dict(policy.scene_risk_levels)
    raw_level = level_by_scene.get(scene_id)
    if raw_level is None:
        raise ValueError(f"chapter policy does not cover scene: {scene_id}")
    level = SceneRiskLevel(raw_level)
    return _DEPTH_BY_LEVEL[level], _BRANCH_BY_LEVEL[level]


def stronger_roleplay_depth(left: str, right: str) -> str:
    """Keep the deeper valid policy without allowing a machine downgrade."""

    if left not in _DEPTH_RANK or right not in _DEPTH_RANK:
        raise ValueError("roleplay depth must be light, targeted, or full")
    return max((left, right), key=_DEPTH_RANK.__getitem__)


def chapter_window_policy(
    window: RollingHorizonWindow,
    profiles: Sequence[SceneRiskProfile],
) -> ChapterWindowPolicy:
    """Project a horizon window and risk profiles into an execution policy."""
    levels = tuple((profile.scene_id, profile.level.value) for profile in profiles)
    branch_count = max(
        (_BRANCH_BY_LEVEL[profile.level] for profile in profiles),
        default=3,
    )
    return ChapterWindowPolicy(
        chapter_id=window.chapter_id,
        active_scene_id=window.active_scene_id,
        deep_scene_ids=window.deep_scene_ids,
        horizon_size=window.horizon_size,
        base_project_revision=window.base_project_revision,
        scene_risk_levels=levels,
        branch_count=branch_count,
        rebase_after=window.rebase_after,
    )


def project_chapter_candidate_parameters(
    candidate_payload: dict[str, object],
    *,
    window: RollingHorizonWindow,
    profiles: Sequence[SceneRiskProfile],
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Project risk-derived depth and branch policy onto a plan candidate."""
    payload = deepcopy(candidate_payload)
    if not profiles:
        return payload, ("chapter-horizon-has-no-risk-profiles",)
    profile_by_scene = {profile.scene_id: profile for profile in profiles}
    _project_strategy(payload, profile_by_scene)
    warnings: list[str] = []
    branch_count = int(payload["strategy"]["branch_count"])
    for node in payload.get("task_nodes") or []:
        if not isinstance(node, dict):
            continue
        kind = node.get("kind")
        if kind == _ROLEPLAY_KIND:
            scene = _first_scoped_scene(node, profile_by_scene)
            if scene is None:
                warnings.append(
                    f"roleplay node has no risk profile: {node.get('node_id', '')}"
                )
                continue
            _set_parameter(
                node,
                "roleplay_depth",
                _DEPTH_BY_LEVEL[profile_by_scene[scene].level],
            )
        elif kind == _BRANCH_KIND:
            _set_parameter(node, "branch_count", branch_count)
    return payload, tuple(warnings)


def _project_strategy(
    payload: dict[str, object],
    profile_by_scene: Mapping[str, SceneRiskProfile],
) -> None:
    strategy = payload.setdefault("strategy", {})
    inventory = list(strategy.get("scene_inventory") or [])
    existing = {
        item["scene_ref"]: item for item in inventory if isinstance(item, dict)
    }
    for scene_ref, profile in profile_by_scene.items():
        entry = existing.get(scene_ref)
        depth = _DEPTH_BY_LEVEL[profile.level]
        if entry is None:
            entry = {
                "scene_ref": scene_ref,
                "function": "",
                "pace": "",
                "roleplay_depth": depth,
            }
            inventory.append(entry)
            existing[scene_ref] = entry
        else:
            entry["roleplay_depth"] = depth
    strategy["scene_inventory"] = inventory
    strategy["branch_count"] = max(
        (_BRANCH_BY_LEVEL[profile.level] for profile in profile_by_scene.values()),
        default=3,
    )


def _first_scoped_scene(
    node: dict[str, object],
    profile_by_scene: Mapping[str, SceneRiskProfile],
) -> str | None:
    for ref in node.get("scope_refs") or []:
        if ref in profile_by_scene:
            return ref
    return None


def _set_parameter(node: dict[str, object], name: str, value: object) -> None:
    parameters = dict(node.get("parameters") or {})
    parameters[name] = value
    node["parameters"] = parameters
