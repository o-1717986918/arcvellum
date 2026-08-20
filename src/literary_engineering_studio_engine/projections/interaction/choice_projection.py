"""Choice collection, action dispatch and supplemental discovery."""

from __future__ import annotations

from pathlib import Path

from ...project_interaction_common import _resolved_choice_ids, _stable_choice_id
from .choice_builders import (
    approval_choice,
    branch_choice,
    candidate_asset_alignment_choice,
    canon_patch_choices,
    direction_choice,
    revision_direction_choice,
    state_patch_choice,
    state_patch_choices,
)
from .style_choices import build_style_mount_choice


class ChoiceCollector:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.choices: list[dict[str, object]] = []
        self._seen: set[str] = set()
        self._resolved = _resolved_choice_ids(root)

    def add(self, choice: dict[str, object] | None, *, step: str = "", next_action: str = "") -> None:
        if not choice:
            return
        if step:
            choice["task_step"] = step
        if next_action:
            choice["next_action"] = next_action
        choice["choice_id"] = _stable_choice_id(choice)
        key = str(choice["choice_id"])
        if key in self._seen or key in self._resolved:
            return
        self._seen.add(key)
        self.choices.append(choice)


def append_action_choice(collector: ChoiceCollector, action: dict[str, object]) -> None:
    route = str(action.get("route") or "")
    step = str(action.get("current_step") or "")
    target = str(action.get("target") or "")
    choice = _choice_for_action(collector.root, route, step, target)
    collector.add(choice, step=step, next_action=str(action.get("next_action") or ""))


def discover_supplemental_choices(collector: ChoiceCollector, route: str) -> None:
    root = collector.root
    if not route or route == "scene-development":
        _discover_unselected_branches(collector)
        for choice in state_patch_choices(root):
            collector.add(choice)
    if not route or route == "review-and-audit":
        for choice in canon_patch_choices(root):
            collector.add(choice)
    if not route or route == "style-engineering":
        collector.add(build_style_mount_choice(root))


def _choice_for_action(
    root: Path,
    route: str,
    step: str,
    target: str,
) -> dict[str, object] | None:
    if step == "asset-approval":
        return approval_choice(root, route, target, "asset_approval", "候选设定需要你确认是否晋升。")
    if step == "release-approval" or route == "export-and-release" and "approval" in step:
        return approval_choice(root, route, target, "release_approval", "发布前需要你确认是否放行。")
    if route == "scene-development":
        return _scene_choice(root, step, target)
    if route == "longform-planning" and step in {"budget-review", "scene-inventory-review", "chapter-obligation-review"}:
        return direction_choice(route, target or "longform", "word_budget_direction")
    return build_style_mount_choice(root) if route == "style-engineering" else None


def _scene_choice(root: Path, step: str, target: str) -> dict[str, object] | None:
    if step == "branch-selection":
        return branch_choice(root, target)
    if step == "candidate-human-decision":
        return candidate_asset_alignment_choice(root, target)
    if step in {"candidate-revision", "static-revision", "revision-direction"}:
        return revision_direction_choice(root, "scene-development", target or "scene", step)
    if step in {"state-writeback", "state-patch-approval"}:
        return state_patch_choice(root, target)
    return None


def _discover_unselected_branches(collector: ChoiceCollector) -> None:
    for manifest in sorted((collector.root / "branches").glob("*/branch_manifest.json")):
        if (manifest.parent / "branch_selection.md").exists():
            continue
        collector.add(branch_choice(collector.root, manifest.parent.name))


__all__ = ["ChoiceCollector", "append_action_choice", "discover_supplemental_choices"]
