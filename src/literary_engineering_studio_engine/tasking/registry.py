"""CLI-mediated task registry for formal platform-agent work."""

from __future__ import annotations

import json
from pathlib import Path
import re

from ..agent_tasks import default_agent_completion_path
from ..longform_planning_route import build_task_payload as _build_longform_route_task_payload
from ..longform_planning_route import validate_task as _validate_longform_route_task
from ..route_selection import (
    select_asset_state,
    select_export_release_state,
    select_longform_state,
    select_review_audit_state,
    select_scene_state,
    select_source_ingest_state,
    select_style_engineering_state,
)
from ..route_catalog import RouteCatalogCallbacks, RouteDefinition, route_definition as _catalog_route_definition
from ..source_ingest_route import build_task_payload as _build_source_ingest_route_task_payload
from ..source_ingest_route import validate_task as _validate_source_ingest_route_task
from ..style_engineering_route import build_task_payload as _build_style_engineering_route_task_payload
from ..style_engineering_route import validate_task as _validate_style_engineering_route_task
from ..asset_route import build_task_payload as _build_asset_route_task_payload
from ..asset_route import validate_task as _validate_asset_route_task
from ..review_audit_route import build_task_payload as _build_review_audit_route_task_payload
from ..review_audit_route import validate_task as _validate_review_audit_route_task
from ..export_release_route import build_task_payload as _build_export_release_route_task_payload
from ..export_release_route import validate_task as _validate_export_release_route_task
from ..scene_development_route import _build_task_payload
from ..scene_development_route import _static_review_conclusion
from ..scene_development_route import blueprint_for_state as _blueprint_for_state
from ..scene_development_route import candidate_review_gate_errors as _candidate_review_gate_errors
from ..scene_development_route import composition_gate_errors as _composition_gate_errors
from ..scene_development_route import validate_task as _state_gate_validation
from ..tasking.package_contract import (
    TASK_CONTRACT_REVISION,
    TASK_TYPE_EXECUTION,
    enrich_task_payload as _enrich_task_contract_payload,
    render_task_markdown as _render_task_contract_markdown,
    task_contract_fingerprint as _task_contract_fingerprint,
)
from ..tasking.lifecycle import (
    LifecycleServices,
    TaskRegistryResult,
    TaskSubmissionResult,
    WorkflowEventsResult,
    advance_workflow as _advance_lifecycle_workflow,
    build_workflow_events as _build_lifecycle_events,
    complete_task as _complete_lifecycle_task,
    issue_next_task as _issue_lifecycle_task,
    open_task as _open_lifecycle_task,
    revert_task_submission as _revert_lifecycle_submission,
    submit_task as _submit_lifecycle_task,
)
from ..tasking.paths import append_event as _append_event
from ..tasking.paths import normalize_route as _normalize_route
from ..tasking.paths import read_json as _read_json
from ..tasking.paths import relative_path as _rel
from ..tasking.paths import resolve_project_path as _resolve_project_path
from ..tasking.paths import task_markdown_path as _task_markdown_path
from ..workflow_state import build_workflow_state, next_scene_workflow_state


SUPPORTED_ROUTES = {
    "scene-development",
    "longform-planning",
    "source-ingest",
    "style-engineering",
    "character-and-world-assets",
    "review-and-audit",
    "export-and-release",
}

def _lifecycle_services() -> LifecycleServices:
    """Inject Registry-owned route rules into route-neutral lifecycle code."""

    return LifecycleServices(
        supported_routes=SUPPORTED_ROUTES,
        build_workflow_state=build_workflow_state,
        route_definition=_route_definition,
        workflow_payload=_workflow_payload,
        enrich_task_payload=_enrich_task_payload,
        render_task_markdown=_render_task_markdown,
        task_contract_fingerprint=_task_contract_fingerprint,
        task_contract_revision=TASK_CONTRACT_REVISION,
        block_task=_block_task,
    )


def issue_next_task(
    project_root: Path,
    *,
    route: str = "scene-development",
    scene: Path | str | None = None,
    force: bool = False,
) -> TaskRegistryResult:
    return _issue_lifecycle_task(
        project_root,
        route=route,
        scene=scene,
        force=force,
        services=_lifecycle_services(),
    )


def open_task(project_root: Path, task_id: str) -> TaskRegistryResult:
    return _open_lifecycle_task(project_root, task_id, services=_lifecycle_services())


def submit_task(
    project_root: Path,
    task_id: str,
    artifacts: list[Path | str],
    *,
    note: str = "",
) -> TaskSubmissionResult:
    return _submit_lifecycle_task(project_root, task_id, artifacts, note=note)


def complete_task(
    project_root: Path,
    task_id: str,
    *,
    handled_by: str = "platform-agent",
    notes: list[str] | None = None,
) -> TaskRegistryResult:
    return _complete_lifecycle_task(
        project_root,
        task_id,
        handled_by=handled_by,
        notes=notes,
        services=_lifecycle_services(),
    )


def revert_task_submission(
    project_root: Path,
    task_id: str,
    *,
    reason: str,
) -> TaskRegistryResult:
    return _revert_lifecycle_submission(project_root, task_id, reason=reason)


def advance_workflow(
    project_root: Path,
    *,
    route: str = "scene-development",
) -> TaskRegistryResult:
    return _advance_lifecycle_workflow(
        project_root,
        route=route,
        services=_lifecycle_services(),
    )


def build_workflow_events(
    project_root: Path,
    *,
    output: Path | None = None,
) -> WorkflowEventsResult:
    return _build_lifecycle_events(project_root, output=output)


def _route_definition(route: str) -> RouteDefinition:
    normalized = _normalize_route(route or "scene-development")
    callbacks = RouteCatalogCallbacks(
        scene_selector=lambda root, payload, scene: select_scene_state(
            root,
            payload,
            scene,
            resolve_project_path=_resolve_project_path,
            relative_path=_rel,
            scene_id_for_path=_scene_id,
        ),
        builders={
            "scene-development": _build_task_payload,
            "longform-planning": _build_longform_route_task_payload,
            "source-ingest": _build_source_ingest_route_task_payload,
            "style-engineering": _build_style_engineering_route_task_payload,
            "character-and-world-assets": _build_asset_route_task_payload,
            "review-and-audit": _build_review_audit_route_task_payload,
            "export-and-release": _build_export_release_route_task_payload,
        },
        validators={
            "scene-development": _state_gate_validation,
            "longform-planning": _validate_longform_route_task,
            "source-ingest": _validate_source_ingest_route_task,
            "style-engineering": _validate_style_engineering_route_task,
            "character-and-world-assets": _validate_asset_route_task,
            "review-and-audit": _validate_review_audit_route_task,
            "export-and-release": _validate_export_release_route_task,
        },
    )
    return _catalog_route_definition(
        normalized,
        callbacks=callbacks,
        selectors={
            "longform-planning": select_longform_state,
            "source-ingest": select_source_ingest_state,
            "style-engineering": select_style_engineering_state,
            "character-and-world-assets": select_asset_state,
            "review-and-audit": select_review_audit_state,
            "export-and-release": select_export_release_state,
        },
    )


def _render_task_markdown(task: dict[str, object], root: Path) -> str:
    """Compatibility facade for the route-independent task contract module."""

    task_id = str(task.get("task_id") or "")
    completion = default_agent_completion_path(_task_markdown_path(root, task_id))
    return _render_task_contract_markdown(task, root, completion_path=completion)


def _enrich_task_payload(task: dict[str, object]) -> dict[str, object]:
    """Compatibility facade retained for existing CLI and test callers."""

    return _enrich_task_contract_payload(task)


def _workflow_payload(root: Path, route: str, scene: Path | str | None = None) -> dict[str, object]:
    if route == "scene-development":
        state = next_scene_workflow_state(root, scene)
        return {"scenes": [state] if state else []}
    result = build_workflow_state(root, route=route)
    return _read_json(result.json_path)


def _scene_id(scene_path: Path) -> str:
    text = scene_path.read_text(encoding="utf-8", errors="ignore") if scene_path.exists() else ""
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    if match:
        scene_id = match.group(1).strip().strip("\"'")
        if scene_id:
            return scene_id
    return scene_path.stem


def _block_task(root: Path, task_json: Path, task: dict[str, object], task_id: str, message: str) -> None:
    task["status"] = "blocked"
    task["validation"] = {"status": "fail", "message": message}
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_blocked", task_id, {"message": message})
