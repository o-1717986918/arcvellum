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


STATE_RULES = [
    "This state ledger is advisory plus auditable; command-level gates remain authoritative.",
    "A step is pass only when the formal CLI artifact and its platform-agent completion marker both exist where required.",
    "Formal Skill hosts must not use allow/unreview/include-blocked debug flags to move the state forward.",
]


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
    scenes, scene_scope_summary = _project_scenes(root, normalized_route, scene, scene_scope)
    route_state = _project_route_state(root, normalized_route)
    summary = _build_summary(normalized_route, scenes, scene_scope_summary, scene_scope, route_state)
    payload = _build_payload(root, normalized_route, scenes, route_state, summary)
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


def _project_scenes(
    root: Path,
    route: str,
    scene: Path | str | None,
    scene_scope: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if route == "scene-development" and scene:
        selected = Path(scene)
        if not selected.is_absolute():
            selected = root / selected
        paths = [selected.resolve()] if selected.is_file() else []
        return [_scene_state(root, path) for path in paths], _scene_scope_summary(root, paths, mode="single")
    if route not in {"scene-development", "overall"}:
        return [], {}
    paths, scope_summary = _scene_paths_for_scope(root, scene_scope)
    return [_scene_state(root, path) for path in paths], scope_summary


def _project_route_state(root: Path, route: str) -> dict[str, object]:
    return {
        "longform": _longform_state(root) if route in {"longform-planning", "overall"} else {},
        "source_ingests": _source_ingest_states(root) if route in {"source-ingest", "overall"} else [],
        "styles": _style_engineering_states(root) if route in {"style-engineering", "overall"} else [],
        "assets": (
            _asset_states(root, include_intake=route == "character-and-world-assets")
            if route in {"character-and-world-assets", "overall"}
            else []
        ),
        "audits": [_review_audit_state(root)] if route in {"review-and-audit", "overall"} else [],
        "exports": _export_release_states(root) if route in {"export-and-release", "overall"} else [],
    }


def _build_summary(
    route: str,
    scenes: list[dict[str, object]],
    scene_scope_summary: dict[str, object],
    scene_scope: str,
    route_state: dict[str, object],
) -> dict[str, object]:
    longform = route_state["longform"]
    collections = [scenes, *[route_state[key] for key in ("source_ingests", "styles", "assets", "audits", "exports")]]
    ready_count = sum(_status_count(items, ready=True) for items in collections)
    blocked_count = sum(_status_count(items, ready=False) for items in collections)
    next_action_count = sum(_action_count(items) for items in collections)
    if isinstance(longform, dict) and longform:
        ready_count += int(longform.get("status") == "ready")
        blocked_count += int(longform.get("status") != "ready")
        next_action_count += int(bool(longform.get("next_action")))
    reported_scene_count = (
        int(scene_scope_summary.get("total_scene_count") or len(scenes))
        if scene_scope == "dashboard"
        else len(scenes)
    )
    return {
        "route": route,
        "scene_count": reported_scene_count,
        "scene_detail_count": len(scenes),
        "scene_scope": scene_scope_summary,
        "source_ingest_count": len(route_state["source_ingests"]),
        "style_profile_count": len(route_state["styles"]),
        "asset_count": len(route_state["assets"]),
        "audit_count": len(route_state["audits"]),
        "export_count": len(route_state["exports"]),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "next_action_count": next_action_count,
        "longform_status": longform.get("status", "") if isinstance(longform, dict) else "",
    }


def _status_count(items: object, *, ready: bool) -> int:
    if not isinstance(items, list):
        return 0
    return sum(1 for item in items if isinstance(item, dict) and (item.get("status") == "ready") is ready)


def _action_count(items: object) -> int:
    if not isinstance(items, list):
        return 0
    return sum(1 for item in items if isinstance(item, dict) and item.get("next_action"))


def _build_payload(
    root: Path,
    route: str,
    scenes: list[dict[str, object]],
    route_state: dict[str, object],
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "schema": "literary-engineering-workbench/formal-route-state/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "route": route,
        "summary": summary,
        "scenes": scenes,
        "longform": route_state["longform"],
        "source_ingests": route_state["source_ingests"],
        "styles": route_state["styles"],
        "assets": route_state["assets"],
        "audits": route_state["audits"],
        "exports": route_state["exports"],
        "rules": list(STATE_RULES),
    }
