"""Human-choice projection and recording public service."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import read_jsonl_tail
from ...project_interaction_common import _now
from ...workflow.dashboard_projection import project_workflow_dashboard
from ...workflow.state import project_workflow_state
from ...workflow_state import next_scene_workflow_state
from .choice_builders import (
    approval_choice,
    asset_approval_source_paths,
    asset_candidate_sha256,
    branch_choice,
    candidate_asset_alignment_choice,
    canon_patch_choices,
    direction_choice,
    file_sha256,
    latest_approval_record,
    revision_direction_choice,
    state_patch_choice,
    state_patch_choices,
)
from .choice_projection import ChoiceCollector, append_action_choice, discover_supplemental_choices
from .choice_recording import (
    finalize_human_choice,
    materialize_approval,
    materialize_branch_selection,
    record_human_choice,
)
from .choice_routes import route_choice_actions
from .style_choices import build_style_mount_choice


def build_current_human_choices(
    project_root: Path,
    route: str = "",
    dashboard_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    normalized_route = str(route or "").strip().lower()
    actions, dashboard_path = _choice_actions(root, normalized_route, dashboard_payload)
    collector = ChoiceCollector(root)
    for action in actions:
        if isinstance(action, dict):
            append_action_choice(collector, action)
    discover_supplemental_choices(collector, normalized_route)
    return {
        "schema": "literary-engineering-workbench/current-human-choices/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "choices": collector.choices[:20],
        "recent_choices": read_jsonl_tail(root / "workflow" / "human_choices" / "index.jsonl", 12),
        "dashboard": dashboard_path,
    }


def _choice_actions(
    root: Path,
    route: str,
    dashboard_payload: dict[str, object] | None,
) -> tuple[list[object], str]:
    if route:
        return _route_choice_actions(root, route)
    if isinstance(dashboard_payload, dict):
        actions = dashboard_payload.get("next_actions")
        return (actions if isinstance(actions, list) else []), "workflow/dashboard/workflow_dashboard.json"
    dashboard = project_workflow_dashboard(root)
    actions = dashboard.get("next_actions")
    return (actions if isinstance(actions, list) else []), "workflow/dashboard/workflow_dashboard.json"


def _route_choice_actions(root: Path, route: str) -> tuple[list[dict[str, object]], str]:
    return route_choice_actions(
        root,
        route,
        project_state=project_workflow_state,
        next_scene_state=next_scene_workflow_state,
    )


# Stable private imports retained for tests and older Studio adapters.
_branch_choice = branch_choice
_approval_choice = approval_choice
_direction_choice = direction_choice
_revision_direction_choice = revision_direction_choice
_candidate_asset_alignment_choice = candidate_asset_alignment_choice
_canon_patch_choices = canon_patch_choices
_state_patch_choices = state_patch_choices
_state_patch_choice = state_patch_choice
_style_mount_choice = build_style_mount_choice
_materialize_branch_selection = materialize_branch_selection
_materialize_approval = materialize_approval
_asset_candidate_sha256 = asset_candidate_sha256
_asset_approval_source_paths = asset_approval_source_paths
_file_sha256 = file_sha256
_latest_approval_record = latest_approval_record


__all__ = ["build_current_human_choices", "finalize_human_choice", "record_human_choice"]
