"""Persistent formal-route state ledger facade.

Route-specific state is deliberately calculated in dedicated modules.  This
facade owns the stable public API, payload assembly, and durable output only.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..atomic_io import atomic_write_text
from .state_assets import _asset_state, _asset_states
from .state_common import _normalize_route, _now, _render_markdown, _resolve_output
from .state_export_release import (
    _export_package_step,
    _export_release_state,
    _export_release_states,
    _release_approval_step,
)
from .state_longform import _longform_state
from .state_review_audit import _review_audit_state
from .state_scene import (
    _composition_step,
    _current_scene_candidate,
    _review_step,
    _scene_paths_for_scope,
    _scene_scope_summary,
    _scene_state,
    _scene_states,
    _static_review_step,
    current_scene_candidate,
    next_scene_workflow_state,
)
from .state_source_ingest import _source_ingest_state, _source_ingest_states
from .state_style import _style_engineering_state, _style_engineering_states


@dataclass(frozen=True)
class WorkflowStateResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    route: str
    scene_count: int
    blocked_count: int
    ready_count: int
    next_action_count: int


def build_workflow_state(
    project_root: Path,
    *,
    route: str = "scene-development",
    scene: Path | str | None = None,
    scene_scope: str = "full",
    output: Path | None = None,
    json_output: Path | None = None,
) -> WorkflowStateResult:
    """Write the current formal-route ledger without advancing any Gate."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    normalized_route = _normalize_route(route) or "scene-development"
    selected_scene_paths: list[Path] = []
    scene_scope_summary: dict[str, object] = {}
    if normalized_route == "scene-development" and scene:
        selected_scene = Path(scene)
        if not selected_scene.is_absolute():
            selected_scene = root / selected_scene
        selected_scene_paths = [selected_scene.resolve()] if selected_scene.is_file() else []
        scenes = [_scene_state(root, path) for path in selected_scene_paths]
        scene_scope_summary = _scene_scope_summary(root, selected_scene_paths, mode="single")
    else:
        if normalized_route in {"scene-development", "overall"}:
            selected_scene_paths, scene_scope_summary = _scene_paths_for_scope(root, scene_scope)
            scenes = [_scene_state(root, path) for path in selected_scene_paths]
        else:
            scenes = []
    longform = _longform_state(root) if normalized_route in {"longform-planning", "overall"} else {}
    source_ingests = _source_ingest_states(root) if normalized_route in {"source-ingest", "overall"} else []
    styles = _style_engineering_states(root) if normalized_route in {"style-engineering", "overall"} else []
    assets = _asset_states(root, include_intake=normalized_route == "character-and-world-assets") if normalized_route in {"character-and-world-assets", "overall"} else []
    audits = [_review_audit_state(root)] if normalized_route in {"review-and-audit", "overall"} else []
    exports = _export_release_states(root) if normalized_route in {"export-and-release", "overall"} else []
    longform_blocked = 1 if longform and longform.get("status") != "ready" else 0
    longform_ready = 1 if longform and longform.get("status") == "ready" else 0
    reported_scene_count = int(scene_scope_summary.get("total_scene_count") or len(scenes)) if scene_scope == "dashboard" else len(scenes)
    summary = {
        "route": normalized_route,
        "scene_count": reported_scene_count,
        "scene_detail_count": len(scenes),
        "scene_scope": scene_scope_summary,
        "source_ingest_count": len(source_ingests),
        "style_profile_count": len(styles),
        "asset_count": len(assets),
        "audit_count": len(audits),
        "export_count": len(exports),
        "ready_count": (
            sum(1 for item in scenes if item["status"] == "ready")
            + longform_ready
            + sum(1 for item in source_ingests if item["status"] == "ready")
            + sum(1 for item in styles if item["status"] == "ready")
            + sum(1 for item in assets if item["status"] == "ready")
            + sum(1 for item in audits if item["status"] == "ready")
            + sum(1 for item in exports if item["status"] == "ready")
        ),
        "blocked_count": (
            sum(1 for item in scenes if item["status"] != "ready")
            + longform_blocked
            + sum(1 for item in source_ingests if item["status"] != "ready")
            + sum(1 for item in styles if item["status"] != "ready")
            + sum(1 for item in assets if item["status"] != "ready")
            + sum(1 for item in audits if item["status"] != "ready")
            + sum(1 for item in exports if item["status"] != "ready")
        ),
        "next_action_count": (
            sum(1 for item in scenes if item.get("next_action"))
            + (1 if longform and longform.get("next_action") else 0)
            + sum(1 for item in source_ingests if item.get("next_action"))
            + sum(1 for item in styles if item.get("next_action"))
            + sum(1 for item in assets if item.get("next_action"))
            + sum(1 for item in audits if item.get("next_action"))
            + sum(1 for item in exports if item.get("next_action"))
        ),
        "longform_status": longform.get("status", "") if isinstance(longform, dict) else "",
    }
    payload = {
        "schema": "literary-engineering-workbench/formal-route-state/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "route": normalized_route,
        "summary": summary,
        "scenes": scenes,
        "longform": longform,
        "source_ingests": source_ingests,
        "styles": styles,
        "assets": assets,
        "audits": audits,
        "exports": exports,
        "rules": [
            "This state ledger is advisory plus auditable; command-level gates remain authoritative.",
            "A step is pass only when the formal CLI artifact and its platform-agent completion marker both exist where required.",
            "Formal Skill hosts must not use allow/unreview/include-blocked debug flags to move the state forward.",
        ],
    }
    markdown_path = _resolve_output(root, output, "workflow", "route_state.md")
    json_path = _resolve_output(root, json_output, "workflow", "route_state.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(markdown_path, _render_markdown(payload))
    return WorkflowStateResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        route=normalized_route,
        scene_count=int(summary["scene_count"]),
        blocked_count=summary["blocked_count"],
        ready_count=summary["ready_count"],
        next_action_count=summary["next_action_count"],
    )
