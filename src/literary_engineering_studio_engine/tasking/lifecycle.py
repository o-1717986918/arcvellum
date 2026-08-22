"""Route-neutral lifecycle operations for formal task packages.

Route-specific work selection and literary gates remain in the Registry.  This
module owns only lifecycle-shaped operations and receives the small set of
Registry services it needs, preventing a circular dependency during the
incremental extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Protocol

from ..agent_tasks import default_agent_completion_path, write_agent_completion_marker
from .paths import (
    SUBMISSION_SCHEMA,
    append_event,
    events_path,
    load_task,
    normalize_route,
    now,
    read_events,
    read_json,
    relative_path,
    render_events_markdown,
    resolve_project_path,
    submission_path,
    task_json_path,
    task_markdown_path,
)
from .supersession import supersede_active_tasks


@dataclass(frozen=True)
class TaskRegistryResult:
    project_root: Path
    task_id: str
    task_json_path: Path | None
    task_markdown_path: Path | None
    status: str
    route: str
    scene_id: str
    current_state: str
    message: str
    expected_output_count: int = 0


@dataclass(frozen=True)
class TaskSubmissionResult:
    project_root: Path
    task_id: str
    task_json_path: Path
    submission_path: Path
    status: str
    artifact_count: int
    message: str


@dataclass(frozen=True)
class WorkflowEventsResult:
    project_root: Path
    events_path: Path
    markdown_path: Path
    event_count: int


class RouteDefinitionLike(Protocol):
    route: str
    ready_message: str

    def select_work_item(self, project_root: Path, state_payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None: ...

    def build_task(self, project_root: Path, route: str, state: dict[str, object]) -> dict[str, object]: ...

    def validate_task(self, project_root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]: ...


@dataclass(frozen=True)
class LifecycleServices:
    supported_routes: set[str]
    build_workflow_state: Callable[..., object]
    route_definition: Callable[[str], RouteDefinitionLike]
    workflow_payload: Callable[[Path, str, Path | str | None], dict[str, object]]
    enrich_task_payload: Callable[[dict[str, object]], dict[str, object]]
    render_task_markdown: Callable[[dict[str, object], Path], str]
    task_contract_fingerprint: Callable[[dict[str, object]], str]
    task_contract_revision: str
    block_task: Callable[[Path, Path, dict[str, object], str, str], None]


def _services_route(services: LifecycleServices, route: str) -> RouteDefinitionLike:
    normalized_route = normalize_route(route or "scene-development")
    if normalized_route not in services.supported_routes:
        raise ValueError(f"task registry supports {', '.join(sorted(services.supported_routes))}, got: {normalized_route}")
    return services.route_definition(normalized_route)


def issue_next_task(
    project_root: Path,
    *,
    route: str = "scene-development",
    scene: Path | str | None = None,
    force: bool = False,
    services: LifecycleServices,
) -> TaskRegistryResult:
    """Issue the next formal task without owning route-specific behavior."""

    root = project_root.resolve()
    normalized_route = normalize_route(route or "scene-development")
    route_def = _services_route(services, normalized_route)
    state_payload = services.workflow_payload(root, normalized_route, scene)
    work_item = route_def.select_work_item(root, state_payload, scene)
    if work_item is None:
        superseded = supersede_active_tasks(
            root,
            route=normalized_route,
            scope_id=None,
            superseded_by="route-ready",
            reason="formal route advanced to ready",
        )
        return _ready_task_result(root, normalized_route, route_def.ready_message, superseded=superseded)

    scene_id = str(work_item.get("scene_id") or work_item.get("target_id") or "")
    current_state = str(work_item.get("current_step") or "")
    if not scene_id or current_state == "ready":
        return _ready_task_result(root, normalized_route, route_def.ready_message, scene_id=scene_id)

    task = services.enrich_task_payload(route_def.build_task(root, normalized_route, work_item))
    identifier = str(task["task_id"])
    task_json = task_json_path(root, identifier)
    task_markdown = task_markdown_path(root, identifier)
    task["task_json"] = relative_path(task_json, root)
    task["task_markdown"] = relative_path(task_markdown, root)

    supersede_active_tasks(
        root,
        route=normalized_route,
        scope_id=scene_id,
        superseded_by=identifier,
        reason=f"formal workflow advanced to {current_state}",
        exclude_task_id=identifier,
    )

    existing_result = _existing_task_result(
        root, task_json, task_markdown, task, force, normalized_route,
        scene_id, current_state, services,
    )
    if existing_result is not None:
        return existing_result

    task_json.parent.mkdir(parents=True, exist_ok=True)
    task_markdown.parent.mkdir(parents=True, exist_ok=True)
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown.write_text(services.render_task_markdown(task, root), encoding="utf-8")
    append_event(root, "task_issued", identifier, {"route": normalized_route, "scene_id": scene_id, "current_state": current_state})
    return TaskRegistryResult(
        project_root=root,
        task_id=identifier,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status="issued",
        route=normalized_route,
        scene_id=scene_id,
        current_state=current_state,
        message="task issued",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def _ready_task_result(
    root: Path,
    route: str,
    message: str,
    *,
    scene_id: str = "",
    superseded: int = 0,
) -> TaskRegistryResult:
    detail = f"{message}; superseded {superseded} obsolete active task(s)" if superseded else message
    return TaskRegistryResult(
        project_root=root,
        task_id="",
        task_json_path=None,
        task_markdown_path=None,
        status="ready",
        route=route,
        scene_id=scene_id,
        current_state="ready",
        message=detail,
    )


def _existing_task_result(
    root: Path,
    task_json: Path,
    task_markdown: Path,
    task: dict[str, object],
    force: bool,
    route: str,
    scene_id: str,
    current_state: str,
    services: LifecycleServices,
) -> TaskRegistryResult | None:
    if force or not task_json.exists():
        return None
    existing = read_json(task_json)
    status = str(existing.get("status") or "")
    if status not in {"issued", "opened", "submitted", "blocked"}:
        return None
    if services.task_contract_fingerprint(existing) != services.task_contract_fingerprint(task):
        task["refreshed_from_status"] = status
        task["refreshed_at"] = now()
        return None
    return TaskRegistryResult(
        project_root=root,
        task_id=str(task["task_id"]),
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status=status,
        route=route,
        scene_id=str(existing.get("scene_id") or scene_id),
        current_state=current_state,
        message="existing active task returned; use --force to refresh",
        expected_output_count=len(existing.get("expected_outputs") or []),
    )


def open_task(project_root: Path, task_id: str, *, services: LifecycleServices) -> TaskRegistryResult:
    """Mark a task as opened and refresh stale task contracts when necessary."""

    root = project_root.resolve()
    task_json = task_json_path(root, task_id)
    stored = load_task(task_json)
    if (
        str(stored.get("status") or "") in {"issued", "opened", "submitted", "blocked"}
        and str(stored.get("task_contract_revision") or "") != services.task_contract_revision
    ):
        refreshed = issue_next_task(root, route=str(stored.get("route") or ""), force=True, services=services)
        if refreshed.task_id != task_id or refreshed.task_json_path is None:
            raise ValueError(
                f"task package is stale; request the current task for route {stored.get('route') or 'unknown'}"
            )
        task_json = refreshed.task_json_path
        stored = load_task(task_json)
    task = services.enrich_task_payload(stored)
    task["status"] = "opened"
    task["opened_at"] = now()
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown = task_markdown_path(root, task_id)
    task_markdown.write_text(services.render_task_markdown(task, root), encoding="utf-8")
    append_event(root, "task_opened", task_id, {"route": task.get("route", ""), "scene_id": task.get("scene_id", "")})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status="opened",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="task opened",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def submit_task(
    project_root: Path,
    task_id: str,
    artifacts: list[Path | str],
    *,
    note: str = "",
) -> TaskSubmissionResult:
    """Record exact platform-agent outputs for one formal task."""

    root = project_root.resolve()
    task_json = task_json_path(root, task_id)
    task = load_task(task_json)
    if str(task.get("execution_policy") or "") == "human-required":
        raise ValueError("human decision tasks are recorded through the Studio decision interface, not task-submit")
    if not artifacts:
        raise ValueError("task-submit requires at least one --from artifact")
    rel_artifacts: list[str] = []
    missing: list[str] = []
    for item in artifacts:
        path = resolve_project_path(root, item)
        relative = relative_path(path, root)
        rel_artifacts.append(relative)
        if not path.exists():
            missing.append(relative)
    if missing:
        raise FileNotFoundError(f"submitted artifacts do not exist: {', '.join(missing)}")
    expected_outputs = {str(item) for item in task.get("expected_outputs") or []}
    submitted_outputs = set(rel_artifacts)
    undeclared = sorted(submitted_outputs - expected_outputs)
    absent = sorted(expected_outputs - submitted_outputs)
    if undeclared:
        raise ValueError(f"submitted artifacts are not declared expected_outputs: {', '.join(undeclared)}")
    if absent:
        raise ValueError(f"task-submit must include every expected output: {', '.join(absent)}")
    target = submission_path(root, task_id)
    payload = {
        "schema": SUBMISSION_SCHEMA,
        "task_id": task_id,
        "route": task.get("route", ""),
        "scene_id": task.get("scene_id", ""),
        "submitted_at": now(),
        "submitted_by": "platform-agent",
        "artifacts": rel_artifacts,
        "note": note,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task["status"] = "submitted"
    task["submission"] = relative_path(target, root)
    task["submitted_artifacts"] = rel_artifacts
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "task_submitted", task_id, {"artifacts": rel_artifacts})
    return TaskSubmissionResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        submission_path=target,
        status="submitted",
        artifact_count=len(rel_artifacts),
        message="task submission recorded",
    )


def complete_task(
    project_root: Path,
    task_id: str,
    *,
    handled_by: str = "platform-agent",
    notes: list[str] | None = None,
    services: LifecycleServices,
) -> TaskRegistryResult:
    """Validate task outputs, write completion evidence, and refresh derived state."""

    root = project_root.resolve()
    task_json = task_json_path(root, task_id)
    task = load_task(task_json)
    if str(task.get("execution_policy") or "") == "human-required":
        raise ValueError("human decision tasks are recorded through the Studio decision interface, not task-complete")
    submitted = submission_path(root, task_id)
    if str(task.get("status") or "") != "submitted" or not submitted.is_file():
        services.block_task(root, task_json, task, task_id, "task-complete requires a prior exact task-submit record")
        raise ValueError("task-complete requires a prior exact task-submit record")
    submission = read_json(submitted)
    expected_outputs = [str(item) for item in task.get("expected_outputs") or []]
    submitted_outputs = {str(item) for item in submission.get("artifacts") or []}
    if str(submission.get("task_id") or "") != task_id or set(expected_outputs) != submitted_outputs:
        services.block_task(root, task_json, task, task_id, "task submission does not exactly match declared expected outputs")
        raise ValueError("task submission does not exactly match declared expected outputs")
    missing = [item for item in expected_outputs if not resolve_project_path(root, item).exists()]
    validation_notes: list[str] = []
    if missing:
        services.block_task(root, task_json, task, task_id, f"missing expected outputs: {', '.join(missing)}")
        raise FileNotFoundError(f"missing expected outputs: {', '.join(missing)}")

    route = str(task.get("route") or "scene-development")
    gate_errors, gate_notes = _services_route(services, route).validate_task(root, task)
    if gate_errors:
        message = "; ".join(gate_errors)
        services.block_task(root, task_json, task, task_id, message)
        raise ValueError(message)
    validation_notes.extend(gate_notes)

    marker_path = task_markdown_path(root, task_id)
    completion_path = default_agent_completion_path(marker_path)
    write_agent_completion_marker(
        marker_path,
        root=root,
        handled_by=handled_by,
        notes=[*(notes or []), *validation_notes],
    )
    task["status"] = "complete"
    task["completed_at"] = now()
    task["completion"] = relative_path(completion_path, root)
    task["validation"] = {"status": "pass", "missing_expected_outputs": [], "notes": validation_notes}
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "task_completed", task_id, {"completion": relative_path(completion_path, root)})
    if route == "scene-development" and task.get("scene"):
        runtime_state = root / "workflow" / "runtime_choices"
        state = services.build_workflow_state(
            root,
            route=route,
            scene=str(task.get("scene") or ""),
            output=runtime_state / "scene-development.md",
            json_output=runtime_state / "scene-development.json",
        )
    else:
        state = services.build_workflow_state(root, route=route)
    append_event(root, "workflow_state_refreshed", task_id, {"state": relative_path(state.json_path, root)})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=marker_path,
        status="complete",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="task completed and workflow state refreshed",
        expected_output_count=len(expected_outputs),
    )


def revert_task_submission(
    project_root: Path,
    task_id: str,
    *,
    reason: str,
) -> TaskRegistryResult:
    """Revoke a failed Worker submission after its output writeback was rolled back."""

    root = project_root.resolve()
    task_json = task_json_path(root, task_id)
    task = load_task(task_json)
    if str(task.get("status") or "") == "complete":
        raise ValueError("cannot revert a completed task submission")
    target = submission_path(root, task_id)
    archived = ""
    if target.exists():
        archive_dir = target.parent / "reverted"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive = archive_dir / f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        target.replace(archive)
        archived = relative_path(archive, root)
    task["status"] = "blocked"
    task.pop("submission", None)
    task.pop("submitted_artifacts", None)
    task["rollback"] = {
        "status": "submission_reverted",
        "reason": reason.strip() or "Studio writeback rolled back after core gate failure",
        "archived_submission": archived,
        "recorded_at": now(),
    }
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "task_submission_reverted", task_id, {"reason": task["rollback"]["reason"], "archived": archived})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=task_markdown_path(root, task_id),
        status="blocked",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="failed submission reverted after writeback rollback",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def advance_workflow(
    project_root: Path,
    *,
    route: str,
    services: LifecycleServices,
) -> TaskRegistryResult:
    """Refresh derived state without allowing manual state jumps."""

    root = project_root.resolve()
    normalized_route = normalize_route(route or "scene-development")
    if normalized_route not in services.supported_routes:
        raise ValueError(f"task registry supports {', '.join(sorted(services.supported_routes))}, got: {normalized_route}")
    state = services.build_workflow_state(root, route=normalized_route)
    append_event(root, "workflow_advanced", "", {"route": normalized_route, "state": relative_path(state.json_path, root)})
    return TaskRegistryResult(
        project_root=root,
        task_id="",
        task_json_path=state.json_path,
        task_markdown_path=state.markdown_path,
        status="refreshed",
        route=normalized_route,
        scene_id="",
        current_state="derived",
        message="workflow state refreshed from artifacts; no manual state override performed",
        expected_output_count=0,
    )


def build_workflow_events(
    project_root: Path,
    *,
    output: Path | None = None,
) -> WorkflowEventsResult:
    root = project_root.resolve()
    source = events_path(root)
    events = read_events(source)
    markdown_path = output if output and output.is_absolute() else root / (output or Path("workflow/events.md"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_events_markdown(events), encoding="utf-8")
    return WorkflowEventsResult(root, source, markdown_path, len(events))
