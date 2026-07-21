"""CLI-mediated task registry for formal platform-agent work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

from .agent_tasks import agent_task_completion_status, default_agent_completion_path, write_agent_completion_marker
from .agent_schema import validate_payload
from .anti_ai_style import style_lint_gate, style_lint_gate_message
from .creative_quality import load_creative_quality_profile
from .asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES, PROMOTABLE_GROUPS
from .asset_context import compact_asset_context_relpaths
from .canon_evolver import canon_writeback_status
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .context_broker import context_trace_status
from .draft_text import final_body_from_draft_path
from .flow_gates import FlowGateError, branch_selection_status, ensure_composition_ready_for_generation
from .longform_materializer import longform_materialization_status, planned_longform_outputs
from .narrative_rhythm import narrative_rhythm_contract
from .prompt_registry import resolve_prompt_asset
from .reader_experience import ensure_reader_experience_ready, reader_experience_adherence_for_body
from .release_fingerprint import release_candidate_fingerprint
from .scene_character_assets import scene_character_asset_requirements
from .style_prompt import style_prompt_quality_report
from .word_budget import ensure_scene_word_budget_ready, word_budget_adherence_for_body
from .workflow_state import build_workflow_state, current_scene_candidate, next_scene_workflow_state


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
SUBMISSION_SCHEMA = "literary-engineering-workbench/agent-submission/v1"
EVENT_SCHEMA = "literary-engineering-workbench/workflow-event/v1"
SUPPORTED_ROUTES = {
    "scene-development",
    "longform-planning",
    "source-ingest",
    "style-engineering",
    "character-and-world-assets",
    "review-and-audit",
    "export-and-release",
}
TASK_TYPE_EXECUTION = {
    "deterministic-cli": ("deterministic", "deterministic-engine"),
    "deterministic-review": ("deterministic", "deterministic-engine"),
    "deterministic-cli-plus-platform-review": ("agent-required", "main-agent"),
    "deterministic-cli-or-repair": ("agent-required", "main-agent"),
    "manual-route-repair": ("agent-required", "main-agent"),
    "human-approval-boundary": ("human-required", "human-decision"),
    "main-platform-agent-prose": ("agent-required", "main-creative-agent"),
    "main-platform-agent-prose-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-creation": ("agent-required", "main-creative-agent"),
    "platform-agent-extraction": ("agent-required", "main-creative-agent"),
    "platform-agent-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-style-prompt": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-review": ("agent-required", "main-review-agent"),
    "platform-agent-evaluation": ("agent-required", "main-review-agent"),
    "platform-agent-judgment": ("agent-required", "main-review-agent"),
    "platform-agent-review": ("agent-required", "main-review-agent"),
    # Historical task packages can be reopened and upgraded in place.
    "deterministic-command": ("deterministic", "deterministic-engine"),
    "human-choice": ("human-required", "human-decision"),
    "platform-agent": ("agent-required", "main-agent"),
    "platform-agent-creative": ("agent-required", "main-creative-agent"),
    "platform-agent-prose": ("agent-required", "main-creative-agent"),
}
HIGH_IMPACT_OUTPUT_PREFIXES = (
    "canon/",
    "characters/",
    "drafts/scenes/",
    "manuscript/",
    "releases/",
    "state/",
)
PROMPT_METADATA_LIST_FIELDS = (
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
)
EXPLICIT_TASK_CONTRACT_FIELDS = {
    "execution_policy",
    "agent_role",
    "human_gate",
    "runtime_capabilities_required",
    "output_contracts",
}


@dataclass(frozen=True)
class RouteDefinition:
    route: str
    ready_message: str
    select_work_item: Callable[[Path, dict[str, object], Path | str | None], dict[str, object] | None]
    build_task: Callable[[Path, str, dict[str, object]], dict[str, object]]
    validate_task: Callable[[Path, dict[str, object]], tuple[list[str], list[str]]]


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


def issue_next_task(
    project_root: Path,
    *,
    route: str = "scene-development",
    scene: Path | str | None = None,
    force: bool = False,
) -> TaskRegistryResult:
    """Issue the next formal platform-agent task from the derived workflow state."""

    root = project_root.resolve()
    normalized_route = _normalize_route(route or "scene-development")
    if normalized_route not in SUPPORTED_ROUTES:
        raise ValueError(f"task registry supports {', '.join(sorted(SUPPORTED_ROUTES))}, got: {normalized_route}")
    route_def = _route_definition(normalized_route)
    state_payload = _workflow_payload(root, normalized_route, scene)
    work_item = route_def.select_work_item(root, state_payload, scene)
    if work_item is None:
        return TaskRegistryResult(
            project_root=root,
            task_id="",
            task_json_path=None,
            task_markdown_path=None,
            status="ready",
            route=normalized_route,
            scene_id="",
            current_state="ready",
            message=route_def.ready_message,
        )
    scene_id = str(work_item.get("scene_id") or work_item.get("target_id") or "")
    current_state = str(work_item.get("current_step") or "")
    if not scene_id or current_state == "ready":
        return TaskRegistryResult(
            project_root=root,
            task_id="",
            task_json_path=None,
            task_markdown_path=None,
            status="ready",
            route=normalized_route,
            scene_id=scene_id,
            current_state="ready",
            message=route_def.ready_message,
        )

    task = _enrich_task_payload(route_def.build_task(root, normalized_route, work_item))
    task_id = str(task["task_id"])
    task_json = _task_json_path(root, task_id)
    task_markdown = _task_markdown_path(root, task_id)
    task["task_json"] = _rel(task_json, root)
    task["task_markdown"] = _rel(task_markdown, root)

    if task_json.exists() and not force:
        existing = _read_json(task_json)
        existing_status = str(existing.get("status") or "")
        if existing_status in {"issued", "opened", "submitted", "blocked"}:
            if _task_contract_fingerprint(existing) == _task_contract_fingerprint(task):
                return TaskRegistryResult(
                    project_root=root,
                    task_id=task_id,
                    task_json_path=task_json,
                    task_markdown_path=task_markdown,
                    status=existing_status,
                    route=normalized_route,
                    scene_id=str(existing.get("scene_id") or scene_id),
                    current_state=current_state,
                    message="existing active task returned; use --force to refresh",
                    expected_output_count=len(existing.get("expected_outputs") or []),
                )
            task["refreshed_from_status"] = existing_status
            task["refreshed_at"] = _now()

    task_json.parent.mkdir(parents=True, exist_ok=True)
    task_markdown.parent.mkdir(parents=True, exist_ok=True)
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")
    _append_event(root, "task_issued", task_id, {"route": normalized_route, "scene_id": scene_id, "current_state": current_state})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=task_markdown,
        status="issued",
        route=normalized_route,
        scene_id=scene_id,
        current_state=current_state,
        message="task issued",
        expected_output_count=len(task.get("expected_outputs") or []),
    )


def _task_contract_fingerprint(task: dict[str, object]) -> str:
    """Hash only the executable contract, excluding lifecycle timestamps/status."""

    fields = {
        key: task.get(key)
        for key in (
            "schema",
            "task_id",
            "route",
            "scene_id",
            "current_state",
            "task_type",
            "prompt_asset_id",
            "command",
            "required_reading",
            "source_paths",
            "expected_outputs",
            "repair_targets",
            "repair_target_sha256",
            "hard_constraints",
            "style_constraints",
            "validation_gates",
            "forbidden_shortcuts",
            "execution_policy",
            "agent_role",
            "human_gate",
            "runtime_capabilities_required",
            "output_contracts",
            "core_managed_outputs",
            "scene_character_assets",
        )
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def open_task(project_root: Path, task_id: str) -> TaskRegistryResult:
    """Mark a task as opened and rewrite its readable task package."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _enrich_task_payload(_load_task(task_json))
    task["status"] = "opened"
    task["opened_at"] = _now()
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_markdown = _task_markdown_path(root, task_id)
    task_markdown.write_text(_render_task_markdown(task, root), encoding="utf-8")
    _append_event(root, "task_opened", task_id, {"route": task.get("route", ""), "scene_id": task.get("scene_id", "")})
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
    """Record platform-agent outputs for a formal task."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _load_task(task_json)
    if str(task.get("execution_policy") or "") == "human-required":
        raise ValueError("human decision tasks are recorded through the Studio decision interface, not task-submit")
    if not artifacts:
        raise ValueError("task-submit requires at least one --from artifact")
    rel_artifacts: list[str] = []
    missing: list[str] = []
    for item in artifacts:
        path = _resolve_project_path(root, item)
        rel = _rel(path, root)
        rel_artifacts.append(rel)
        if not path.exists():
            missing.append(rel)
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
    submission_path = _submission_path(root, task_id)
    payload = {
        "schema": SUBMISSION_SCHEMA,
        "task_id": task_id,
        "route": task.get("route", ""),
        "scene_id": task.get("scene_id", ""),
        "submitted_at": _now(),
        "submitted_by": "platform-agent",
        "artifacts": rel_artifacts,
        "note": note,
    }
    submission_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task["status"] = "submitted"
    task["submission"] = _rel(submission_path, root)
    task["submitted_artifacts"] = rel_artifacts
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_submitted", task_id, {"artifacts": rel_artifacts})
    return TaskSubmissionResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        submission_path=submission_path,
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
) -> TaskRegistryResult:
    """Validate task outputs and write the formal completion marker."""

    root = project_root.resolve()
    task_json = _task_json_path(root, task_id)
    task = _load_task(task_json)
    if str(task.get("execution_policy") or "") == "human-required":
        raise ValueError("human decision tasks are recorded through the Studio decision interface, not task-complete")
    submission_path = _submission_path(root, task_id)
    if str(task.get("status") or "") != "submitted" or not submission_path.is_file():
        _block_task(root, task_json, task, task_id, "task-complete requires a prior exact task-submit record")
        raise ValueError("task-complete requires a prior exact task-submit record")
    submission = _read_json(submission_path)
    expected_outputs = [str(item) for item in task.get("expected_outputs") or []]
    submitted_outputs = {str(item) for item in submission.get("artifacts") or []}
    if str(submission.get("task_id") or "") != task_id or set(expected_outputs) != submitted_outputs:
        _block_task(root, task_json, task, task_id, "task submission does not exactly match declared expected outputs")
        raise ValueError("task submission does not exactly match declared expected outputs")
    missing = [item for item in expected_outputs if not _resolve_project_path(root, item).exists()]
    validation_notes: list[str] = []
    if missing:
        _block_task(root, task_json, task, task_id, f"missing expected outputs: {', '.join(missing)}")
        raise FileNotFoundError(f"missing expected outputs: {', '.join(missing)}")

    route = str(task.get("route") or "scene-development")
    gate_errors, gate_notes = _route_definition(route).validate_task(root, task)
    if gate_errors:
        message = "; ".join(gate_errors)
        _block_task(root, task_json, task, task_id, message)
        raise ValueError(message)
    validation_notes.extend(gate_notes)

    completion_path = default_agent_completion_path(_task_markdown_path(root, task_id))
    write_agent_completion_marker(
        _task_markdown_path(root, task_id),
        root=root,
        handled_by=handled_by,
        notes=[*(notes or []), *validation_notes],
    )
    task["status"] = "complete"
    task["completed_at"] = _now()
    task["completion"] = _rel(completion_path, root)
    task["validation"] = {"status": "pass", "missing_expected_outputs": [], "notes": validation_notes}
    task_json.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(root, "task_completed", task_id, {"completion": _rel(completion_path, root)})
    if route == "scene-development" and task.get("scene"):
        runtime_state = root / "workflow" / "runtime_choices"
        state = build_workflow_state(
            root,
            route=route,
            scene=str(task.get("scene") or ""),
            output=runtime_state / "scene-development.md",
            json_output=runtime_state / "scene-development.json",
        )
    else:
        state = build_workflow_state(root, route=route)
    _append_event(root, "workflow_state_refreshed", task_id, {"state": _rel(state.json_path, root)})
    return TaskRegistryResult(
        project_root=root,
        task_id=task_id,
        task_json_path=task_json,
        task_markdown_path=_task_markdown_path(root, task_id),
        status="complete",
        route=str(task.get("route") or ""),
        scene_id=str(task.get("scene_id") or ""),
        current_state=str(task.get("current_state") or ""),
        message="task completed and workflow state refreshed",
        expected_output_count=len(expected_outputs),
    )


def advance_workflow(
    project_root: Path,
    *,
    route: str = "scene-development",
) -> TaskRegistryResult:
    """Refresh the derived workflow state without allowing manual state jumps."""

    root = project_root.resolve()
    normalized_route = _normalize_route(route or "scene-development")
    if normalized_route not in SUPPORTED_ROUTES:
        raise ValueError(f"task registry supports {', '.join(sorted(SUPPORTED_ROUTES))}, got: {normalized_route}")
    state = build_workflow_state(root, route=normalized_route)
    _append_event(root, "workflow_advanced", "", {"route": normalized_route, "state": _rel(state.json_path, root)})
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
    events_path = _events_path(root)
    events = _read_events(events_path)
    markdown_path = output if output and output.is_absolute() else root / (output or Path("workflow/events.md"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(_render_events_markdown(events), encoding="utf-8")
    return WorkflowEventsResult(root, events_path, markdown_path, len(events))


def _route_definition(route: str) -> RouteDefinition:
    normalized = _normalize_route(route or "scene-development")
    definitions = {
        "scene-development": RouteDefinition(
            route="scene-development",
            ready_message="no pending scene-development task found",
            select_work_item=_select_scene_state,
            build_task=_build_task_payload,
            validate_task=_state_gate_validation,
        ),
        "longform-planning": RouteDefinition(
            route="longform-planning",
            ready_message="longform-planning route is ready",
            select_work_item=_select_longform_state,
            build_task=_build_longform_task_payload,
            validate_task=_longform_state_gate_validation,
        ),
        "source-ingest": RouteDefinition(
            route="source-ingest",
            ready_message="source-ingest route has no pending imported source",
            select_work_item=_select_source_ingest_state,
            build_task=_build_source_ingest_task_payload,
            validate_task=_source_ingest_state_gate_validation,
        ),
        "style-engineering": RouteDefinition(
            route="style-engineering",
            ready_message="style-engineering route has no pending style profile",
            select_work_item=_select_style_engineering_state,
            build_task=_build_style_engineering_task_payload,
            validate_task=_style_engineering_state_gate_validation,
        ),
        "character-and-world-assets": RouteDefinition(
            route="character-and-world-assets",
            ready_message="character-and-world-assets route has no pending candidate asset",
            select_work_item=_select_asset_state,
            build_task=_build_asset_task_payload,
            validate_task=_asset_state_gate_validation,
        ),
        "review-and-audit": RouteDefinition(
            route="review-and-audit",
            ready_message="review-and-audit route is ready",
            select_work_item=_select_review_audit_state,
            build_task=_build_review_audit_task_payload,
            validate_task=_review_audit_state_gate_validation,
        ),
        "export-and-release": RouteDefinition(
            route="export-and-release",
            ready_message="export-and-release route has no pending chapter",
            select_work_item=_select_export_release_state,
            build_task=_build_export_release_task_payload,
            validate_task=_export_release_state_gate_validation,
        ),
    }
    try:
        return definitions[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported route: {route}") from exc


def _build_task_payload(root: Path, route: str, scene_state: dict[str, object]) -> dict[str, object]:
    scene_id = str(scene_state.get("scene_id") or "")
    scene_rel = str(scene_state.get("scene") or f"scenes/{scene_id}.yaml")
    current_state = str(scene_state.get("current_step") or "")
    next_action = str(scene_state.get("next_action") or "")
    blueprint = _blueprint_for_state(root, scene_id, scene_rel, current_state, next_action)
    task_id = _task_id(route, scene_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": scene_id,
        "scene": scene_rel,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": [
            "SKILL.md",
            "AGENTS.md",
            "agentread.yaml",
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/punctuation-standard.md",
        ],
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": blueprint.get("word_count_min", 0),
        "word_count_max": blueprint.get("word_count_max", 0),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not hand-write same-named formal files to bypass the documented command.",
            "Do not use debug/bypass flags such as --allow-unreviewed, --allow-review-notes, --include-blocked, --allow-unapproved, --allow-missing-composition, --allow-unselected-composition, --allow-recommended-branch, or --allow-missing-branch.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
            "Do not let subagents draft, revise, polish, expand, or finalize creative body text.",
            "Do not write API keys or provider secrets into the work project.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    for key in ("candidate", "revision_source"):
        if blueprint.get(key):
            payload[key] = blueprint[key]
    if blueprint.get("scene_character_assets"):
        payload["scene_character_assets"] = blueprint["scene_character_assets"]
    if blueprint.get("core_managed_outputs"):
        payload["core_managed_outputs"] = [str(item) for item in blueprint["core_managed_outputs"]]
    if current_state in {"candidate-revision", "static-revision"} and blueprint.get("revision_source"):
        source = _resolve_project_path(root, str(blueprint["revision_source"]))
        if source.is_file():
            payload["candidate_sha256_before_revision"] = _file_sha256(source)
    return payload


def _build_longform_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _longform_blueprint_for_state(root, current_state, next_action)
    task_id = _task_id(route, "longform", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": "longform",
        "target_id": "longform",
        "scene": "project.yaml",
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "docs/modules/longform-word-budget.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": blueprint.get("word_count_min", 0),
        "word_count_max": blueprint.get("word_count_max", 0),
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat word_budget.json as final plot or sufficient narrative inventory by itself.",
            "Do not bypass word_budget.agent_tasks.md or scene_inventory_expansion.agent_tasks.md.",
            "Do not start bulk scene generation while longform-planning is blocked.",
            "Do not satisfy target length by making each scene verbose; expand narrative inventory instead.",
            "Do not overwrite formal plot/outline.md or scenes/ before candidate review and user approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(_resolve_project_path(root, relative))
            for relative in repair_targets
            if _resolve_project_path(root, relative).is_file()
        }
    return payload


def _build_source_ingest_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    work_id = str(state.get("work_id") or state.get("target_id") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    import_dir = str(state.get("import_dir") or f"sources/imports/{work_id}")
    blueprint = _source_ingest_blueprint_for_state(root, work_id, import_dir, current_state, next_action)
    task_id = _task_id(route, work_id or "source", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": work_id,
        "target_id": work_id,
        "work_id": work_id,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write source-derived material directly into canon, character, plot, draft, export, or release files.",
            "Do not treat extracted claims as confirmed facts without evidence_refs, confidence, unknowns, contradiction notes, review, and approval.",
            "Do not skip extract_project_files.agent_tasks.md after source-ingest creates it.",
            "Do not copy long source passages into extraction reports.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(_resolve_project_path(root, relative))
            for relative in repair_targets
            if _resolve_project_path(root, relative).is_file()
        }
    return payload


def _build_style_engineering_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    profile_id = str(state.get("profile_id") or state.get("target_id") or "")
    profile_dir = str(state.get("profile_dir") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _style_engineering_blueprint_for_state(root, profile_id, profile_dir, current_state, next_action)
    task_id = _task_id(route, profile_id or "style-profile", current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": profile_id,
        "target_id": profile_id,
        "profile_id": profile_id,
        "profile_dir": profile_dir,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/workflows.md",
                "docs/modules/style-compiler.md",
                "docs/implementation/phase26-style-prompt-effectiveness.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not mount a Style Skill from an under-specified prompt.",
            "Do not use --allow-unreviewed for formal Skill-host work.",
            "Do not treat style metrics or a dry profile report as an LLM-facing prompt.",
            "Do not pursue exact author imitation unless the corpus is public-domain, authorized, or user-owned.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(_resolve_project_path(root, relative))
            for relative in repair_targets
            if _resolve_project_path(root, relative).is_file()
        }
    return payload


def _build_asset_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    candidate_id = str(state.get("candidate_id") or state.get("target_id") or "asset-intake")
    asset_type = str(state.get("asset_type") or "")
    candidate = str(state.get("candidate") or "")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _asset_blueprint_for_state(root, candidate_id, asset_type, candidate, current_state, next_action)
    task_id = _task_id(route, candidate_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": candidate_id,
        "target_id": candidate_id,
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "candidate": candidate,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
                "docs/implementation/phase38-agent-character-creation.md",
                "docs/implementation/phase41-candidate-review-promotion.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not write directly into canon/, characters/, plot/outline.md, scenes/, drafts/, exports/, or releases/ from a candidate task.",
            "Do not promote any candidate asset without a clean platform-agent asset review and an approve record.",
            "Do not use --allow-unapproved or any debug approval bypass in formal Skill-host work.",
            "Do not let extracted/source-derived claims become canon without evidence_refs, confidence, review, and approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    if current_state in {"asset-review-pass", "asset-approval-revision"} and candidate:
        candidate_path = _resolve_project_path(root, candidate)
        if candidate_path.is_file():
            payload["candidate_sha256_before_revision"] = _file_sha256(candidate_path)
    return payload


def _build_review_audit_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _review_audit_blueprint_for_state(root, current_state, next_action, state)
    target_id = str(state.get("patch_id") or "project-review")
    task_id = _task_id(route, target_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    payload = {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": str(state.get("scene_id") or "project-review"),
        "target_id": target_id,
        "patch": str(state.get("patch") or ""),
        "patch_id": str(state.get("patch_id") or ""),
        "candidate_sha256": str(state.get("candidate_sha256") or ""),
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
                "docs/implementation/phase30-agent-canon-review.md",
                "docs/implementation/phase33-agent-review-committee.md",
                "docs/implementation/phase8-longform-audit.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": 0,
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat canon-lint or longform-audit as a semantic review by themselves.",
            "Do not use local dry-run/http-chat provider output as the formal review judgment.",
            "Do not let review pass_with_notes, unresolved facts, timeline risks, committee action_items, or disagreements move into export/release.",
            "A semantic review task must not edit project sources. A formal revision task may edit only its exact declared repair_targets inside the isolated sandbox.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: _file_sha256(_resolve_project_path(root, relative))
            for relative in repair_targets
            if _resolve_project_path(root, relative).is_file()
        }
    return payload


def _build_export_release_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    chapter_id = str(state.get("chapter_id") or state.get("target_id") or "chapter_0001")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = _export_release_blueprint_for_state(root, chapter_id, current_state, next_action)
    task_id = _task_id(route, chapter_id, current_state)
    expected_outputs = _unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = _unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    now = _now()
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": now,
        "route": route,
        "scene_id": chapter_id,
        "target_id": chapter_id,
        "chapter_id": chapter_id,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": blueprint.get(
            "required_reading",
            [
                "SKILL.md",
                "AGENTS.md",
                "agentread.yaml",
                "references/agent-run-protocol.md",
                "references/cli-run-protocol.md",
                "references/artifact-contracts.md",
                "references/workflows.md",
                "references/file-format-export.md",
                "docs/implementation/phase7-chapter-pipeline.md",
                "docs/implementation/phase9-export-package.md",
                "docs/implementation/phase21-publish-chain.md",
            ],
        ),
        "source_paths": source_paths,
        "context_trace": blueprint.get("context_trace", ""),
        "hard_constraints": blueprint["hard_constraints"],
        "style_constraints": blueprint["style_constraints"],
        "word_count_target": blueprint.get("word_count_target", 0),
        "word_count_min": 0,
        "word_count_max": 0,
        "expected_outputs": expected_outputs,
        "submission_command": f"python -m literary_engineering_studio_engine task-submit <project> --task-id {task_id} --from <artifact>",
        "completion_command": f"python -m literary_engineering_studio_engine task-complete <project> --task-id {task_id}",
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not use --include-blocked, --allow-unapproved, or custom export scripts for formal delivery.",
            "Do not export chapters with non-ready scenes, unresolved review notes, pending sidecars, skipped scenes, or workflow traces.",
            "Do not include scene ids, canon notes, review text, state patches, AGENT_TASK markers, or writeback candidates in final delivery files.",
            "Do not publish without a human approve record matching the release run id.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _blueprint_for_state(root: Path, scene_id: str, scene_rel: str, current_state: str, next_action: str) -> dict[str, object]:
    scene_path = _resolve_project_path(root, scene_rel)
    scene_text = _read_text(scene_path)
    chapter_match = re.search(r"(?m)^[ \t]*chapter_obligation_id:[ \t]*['\"]?([^'\"\n#]+)", scene_text) or re.search(
        r"(?m)^[ \t]*chapter_id:[ \t]*['\"]?([^'\"\n#]+)", scene_text
    )
    chapter_id = chapter_match.group(1).strip().strip("\"'") if chapter_match else "chapter_0001"
    context = f"memory/context_packets/{scene_id}.md"
    context_trace = f"memory/context_packets/{scene_id}.trace.json"
    branch_dir = f"branches/{scene_id}"
    composition = f"drafts/compositions/{scene_id}_composition"
    current_candidate = current_scene_candidate(root, scene_id)
    candidate_markdown = (
        _rel(current_candidate, root)
        if current_candidate is not None
        else f"drafts/candidates/{scene_id}-platform-agent.md"
    )
    candidate = candidate_markdown[:-3] if candidate_markdown.endswith(".md") else candidate_markdown
    review = f"reviews/agent/{scene_id}_scene_review"
    review_path = root / f"{review}.json"
    review_payload = _read_json(review_path) if review_path.is_file() else {}
    revision_source = str(
        review_payload.get("candidate")
        or review_payload.get("reviewed_candidate")
        or review_payload.get("draft")
        or f"{candidate}.md"
    ).replace("\\", "/")
    if Path(revision_source).is_absolute():
        revision_source = _rel(Path(revision_source), root)
    if current_state == "static-revision":
        revision_source = f"drafts/scenes/{scene_id}.md"
    revision = f"drafts/revisions/{scene_id}_revision"
    state_patch = f"characters/state_patches/{scene_id}_state_patch"
    canon_patch = f"canon/patches/{scene_id}_canon_patch"
    direction_sources = (
        ["workflow/studio/user_directions.md"]
        if (root / "workflow" / "studio" / "user_directions.md").is_file()
        else []
    )
    common_sources = [scene_rel]
    context_sources = _context_source_paths(root, scene_rel)
    roleplay_task = f"{branch_dir}/roleplay_simulation.agent_tasks.md"
    roleplay_completion = f"{branch_dir}/roleplay_simulation.agent_completion.json"
    branch_task = f"{branch_dir}/branch_manifest.agent_tasks.md"
    branch_completion = f"{branch_dir}/branch_manifest.agent_completion.json"
    composition_task = f"{composition}.agent_tasks.md"
    composition_completion = f"{composition}.agent_completion.json"
    chapter_contract_sources = [
        f"plot/chapter_obligations/{chapter_id}.json",
        f"plot/chapter_obligations/{chapter_id}.md",
        f"plot/chapter_obligations/{chapter_id}.agent_tasks.md",
        f"plot/chapter_obligations/{chapter_id}.agent_completion.json",
        "plot/rhythm_plan.json",
    ]
    # These are not decorative planning artifacts: generate-scene verifies the
    # budget sidecar and its review before creating a prose task.  Carry the
    # evidence into the sandbox so a controlled worker observes the same gate
    # result as the project root.
    longform_budget_evidence_sources = [
        "plot/word_budget/word_budget.agent_tasks.md",
        "plot/word_budget/word_budget.agent_completion.json",
        "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
        "plot/word_budget/scene_inventory_expansion.agent_completion.json",
        "reviews/word_budget/word_budget_review.md",
        "reviews/word_budget/scene_inventory_review.md",
        "reviews/word_budget/chapter_obligation_review.md",
    ]
    scene_runtime_sources = list(
        dict.fromkeys(
            [
                *context_sources,
                context,
                context_trace,
                *chapter_contract_sources,
                *longform_budget_evidence_sources,
            ]
        )
    )
    scene_character_assets = scene_character_asset_requirements(root, scene_path)
    scene_character_asset_outputs = [
        relative
        for requirement in scene_character_assets
        for relative in (
            _rel(requirement.candidate_path, root),
            _rel(requirement.report_path, root),
            _rel(requirement.task_path, root),
            _rel(requirement.completion_path, root),
        )
    ]
    table: dict[str, dict[str, object]] = {
        "context-packet": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.context.v1",
            "command": f"python -m literary_engineering_studio_engine context <project> --scene {scene_rel}",
            "source_paths": context_sources,
            "context_trace": context_trace,
            "expected_outputs": [context, context_trace, "memory/index.json"],
            "hard_constraints": ["Run the documented context command; inspect both the context packet and context trace before submitting."],
            "style_constraints": [],
            "validation_gates": ["context packet exists", "context trace exists and validates loaded source groups"],
            "next_allowed_states": ["roleplay-simulation"],
        },
        "context-trace": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.context.trace.v1",
            "command": f"python -m literary_engineering_studio_engine context <project> --scene {scene_rel}",
            "source_paths": list(dict.fromkeys([*context_sources, context])),
            "context_trace": context_trace,
            "expected_outputs": [context, context_trace, "memory/index.json"],
            "hard_constraints": [
                "The existing context packet is not formal without its context trace.",
                "Rerun the documented context command and inspect the trace before moving to roleplay.",
            ],
            "style_constraints": [],
            "validation_gates": ["context trace exists", "context trace validates loaded source groups"],
            "next_allowed_states": ["roleplay-simulation"],
        },
        "roleplay-simulation": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.roleplay.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine simulate-scene <project> --scene {scene_rel} --agent",
            "source_paths": scene_runtime_sources,
            "context_trace": context_trace,
            "expected_outputs": [f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md"],
            "hard_constraints": ["Use --agent so the platform-agent RP task is emitted as a sidecar."],
            "style_constraints": [],
            "validation_gates": ["roleplay simulation exists", "roleplay sidecar exists"],
            "next_allowed_states": ["roleplay-agent-task"],
        },
        "roleplay-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.roleplay.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{branch_dir}/roleplay_simulation.md", f"{branch_dir}/roleplay_simulation.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{branch_dir}/roleplay_simulation.agent_completion.json"],
            "hard_constraints": [
                "Read the roleplay sidecar and fill roleplay/world/branch/canon/writeback reasoning as platform agent.",
                "Create the original roleplay_simulation.agent_completion.json before continuing.",
            ],
            "style_constraints": [],
            "validation_gates": ["roleplay sidecar completion marker exists"],
            "next_allowed_states": ["branch-manifest"],
        },
        "branch-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.branch.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine branch-simulate <project> --scene {scene_rel} --agent",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{branch_dir}/roleplay_simulation.md",
                roleplay_task,
                roleplay_completion,
            ])),
            "context_trace": context_trace,
            "expected_outputs": [
                f"{branch_dir}/branch_simulation.md",
                f"{branch_dir}/branch_manifest.json",
                f"{branch_dir}/branch_manifest.agent_tasks.md",
                f"{branch_dir}/branch_selection.md",
            ],
            "hard_constraints": ["Use --agent so branch review and selection tasks are emitted."],
            "style_constraints": [],
            "validation_gates": ["branch manifest exists", "branch sidecar exists"],
            "next_allowed_states": ["branch-agent-task"],
        },
        "branch-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{branch_dir}/branch_simulation.md", f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_manifest.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{branch_dir}/branch_selection.md", f"{branch_dir}/branch_manifest.agent_completion.json"],
            "hard_constraints": ["Read branch candidates, write formal selected decision, and complete the branch sidecar marker."],
            "style_constraints": [],
            "validation_gates": ["branch_selection.md exists", "branch sidecar completion marker exists"],
            "next_allowed_states": ["branch-selection"],
        },
        "branch-selection": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.branch.selection.v1",
            "command": "",
            "source_paths": [scene_rel, f"{branch_dir}/branch_manifest.json", f"{branch_dir}/branch_selection.md"],
            "expected_outputs": [f"{branch_dir}/branch_selection.md"],
            "hard_constraints": ["branch_selection.md must contain decision: selected and selected_branch before composition."],
            "style_constraints": [],
            "validation_gates": ["branch_selection_status == selected"],
            "next_allowed_states": ["composition-json"],
        },
        "composition-json": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.composition.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine compose-scene <project> --scene {scene_rel} --agent-tasks",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{branch_dir}/branch_manifest.json",
                f"{branch_dir}/branch_selection.md",
                branch_task,
                branch_completion,
            ])),
            "context_trace": context_trace,
            "expected_outputs": [f"{composition}.md", f"{composition}.json", f"{composition}.agent_tasks.md"],
            "hard_constraints": ["Composition must use formal branch_selection and created_by=compose-scene provenance."],
            "style_constraints": [],
            "validation_gates": ["composition JSON exists", "composition sidecar exists"],
            "next_allowed_states": ["composition-agent-task"],
        },
        "composition-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.composition.execute.v1",
            "command": "",
            "source_paths": list(dict.fromkeys([
                *scene_runtime_sources,
                f"{composition}.md",
                f"{composition}.json",
                f"{composition}.agent_tasks.md",
            ])),
            "context_trace": context_trace,
            "expected_outputs": [f"{composition}.agent_completion.json"],
            "hard_constraints": ["Read the composition sidecar, perform platform-agent composition review, and complete the marker."],
            "style_constraints": [],
            "validation_gates": ["composition sidecar completion marker exists"],
            "next_allowed_states": ["scene-word-budget-contract"],
        },
        "scene-word-budget-contract": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.scene-budget.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, "project.yaml", "plot/word_budget/word_budget.json"],
            "context_trace": context_trace,
            "expected_outputs": ["plot/word_budget/word_budget.json"],
            "hard_constraints": [
                "This state validates the existing formal longform budget; create or repair the budget through the longform-planning route.",
                "Longform scenes must carry word_count_target/min/max before formal generation.",
            ],
            "style_constraints": [],
            "validation_gates": ["scene word budget contract passes or is not required"],
            "next_allowed_states": ["reader-experience-contract"],
        },
        "reader-experience-contract": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.longform-planning.reader-experience.v1",
            "command": f"python -m literary_engineering_studio_engine chapter-obligation <project> --chapter-id {chapter_id}",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        "scenes",
                        "plot/word_budget/word_budget.json",
                        "plot/chapter_obligations/",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [
                f"plot/chapter_obligations/{chapter_id}.json",
                f"plot/chapter_obligations/{chapter_id}.md",
                f"plot/chapter_obligations/{chapter_id}.agent_tasks.md",
                f"plot/chapter_obligations/{chapter_id}.agent_completion.json",
            ],
            "hard_constraints": [
                "Longform scenes must have a ready chapter obligation and reader-experience contract before prose generation.",
                "The platform agent must fill reader_question, promised_reward, withheld_information, payoff_or_delay, emotional_curve, tension_source, curiosity_hook, freshness_requirement, anti_summary_requirement, and reader_aftertaste for this scene.",
            ],
            "style_constraints": ["Do not turn reader-experience notes into visible workflow text inside prose."],
            "validation_gates": ["reader-experience contract passes or is not required"],
            "next_allowed_states": ["scene-rhythm-contract"],
        },
        "scene-rhythm-contract": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.scene-development.rhythm.contract.v1",
            "command": "",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        "scenes",
                        "plot/rhythm_plan.json",
                        f"plot/chapter_obligations/{chapter_id}.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [scene_rel],
            "hard_constraints": [
                "Write explicit narrative_rhythm.tension_curve entry/peak/exit values from 1 to 5 and scene_bridge.incoming_pressure.",
                "Preserve scene facts and do not draft prose, alter canon, or create a branch decision in this task.",
                "For an opening scene, document its baseline pressure rather than leaving incoming_pressure blank.",
            ],
            "style_constraints": ["Specify uneven pacing through scene function, density, turn, and bridge; avoid a uniform high-pressure rhythm."],
            "validation_gates": ["narrative rhythm/bridge contract passes"],
            "next_allowed_states": ["composition-json"],
        },
        "candidate-generation-provenance": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.generate.v1",
            "command": f"python -m literary_engineering_studio_engine generate-scene <project> --scene {scene_rel} --materialization-scope scene",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        f"{composition}.md",
                        f"{composition}.json",
                        roleplay_task,
                        roleplay_completion,
                        branch_task,
                        branch_completion,
                        composition_task,
                        composition_completion,
                        f"{branch_dir}/branch_selection.md",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [
                f"{candidate}.md",
                f"{candidate}.json",
                f"{candidate}.prompt.json",
                f"{candidate}.agent_tasks.md",
                f"{candidate}.agent_completion.json",
                *scene_character_asset_outputs,
            ],
            "hard_constraints": [
                "Run generate-scene to obtain prompt manifest and sidecar, then the main platform agent personally writes the candidate body.",
                "The candidate must not be drafted by a subagent and must not include workflow traces.",
                *(
                    [
                        "This scene declares named participants without formal character files. Run generate-scene, read each emitted character candidate sidecar, and create its schema-valid candidate JSON/report/completion before drafting prose.",
                        "Record those candidates in new_character_register with status=candidates_ready and an empty blocking_issues list. Do not promote them or pretend they are already formal characters.",
                    ]
                    if scene_character_assets
                    else []
                ),
            ],
            "style_constraints": [
                "Apply mounted Style Skill first at expression level.",
                "Apply punctuation standard, Style Lint Gate, and anti-evasion rules before submitting.",
            ],
            "validation_gates": ["candidate Markdown exists", "candidate manifest exists", "prompt manifest exists", "generation sidecar completion marker exists"],
            "next_allowed_states": ["generation-agent-task", "candidate-review"],
            "scene_character_assets": [item.as_dict(root) for item in scene_character_assets],
            "core_managed_outputs": [
                f"{candidate}.prompt.json",
                f"{candidate}.agent_tasks.md",
                *[_rel(item.task_path, root) for item in scene_character_assets],
            ],
        },
        "generation-agent-task": {
            "task_type": "main-platform-agent-prose",
            "prompt_asset_id": "route.scene-development.prose.complete.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{candidate}.prompt.json", f"{candidate}.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{candidate}.md", f"{candidate}.json", f"{candidate}.agent_completion.json"],
            "hard_constraints": ["Complete the generate-scene sidecar after candidate Markdown and manifest are checked."],
            "style_constraints": ["Candidate must satisfy style, punctuation, word budget, and anti-evasion protocol before completion."],
            "validation_gates": ["generation sidecar completion marker exists"],
            "next_allowed_states": ["candidate-review"],
        },
        "candidate-review": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.v1",
            "command": f"python -m literary_engineering_studio_engine agent-review-scene <project> --scene {scene_rel} --draft {candidate}.md --materialization-scope scene",
            "candidate": f"{candidate}.md",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        f"{candidate}.md",
                        f"{candidate}.json",
                        "schemas/agent_outputs/scene_review.v1.schema.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_tasks.md", f"{review}.agent_completion.json"],
            "core_managed_outputs": [f"{review}.agent_tasks.md"],
            "hard_constraints": [
                "Review the exact candidate path; pass_with_notes, warnings, or revision actions block promotion.",
                "A non-pass verdict is a valid completed review and must remain available to the formal candidate-revision task.",
                "Do not edit prose in this review task and do not soften findings to make the route advance.",
            ],
            "style_constraints": ["Handle deterministic Style Lint evidence and anti-evasion risks explicitly."],
            "validation_gates": ["scene_review.v1 JSON exists", "review cites exact candidate", "review conclusion is recorded", "new_character_register is recorded"],
            "next_allowed_states": ["candidate-revision", "agent-review-task", "promotion-manifest"],
        },
        "candidate-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.scene-development.revision.v1",
            "command": f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} --draft {revision_source} --review {review}.json",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        revision_source,
                        f"{review}.json",
                        f"{review}.md",
                        *direction_sources,
                    ]
                )
            ),
            "context_trace": context_trace,
            "candidate": f"{revision}.md",
            "revision_source": revision_source,
            "expected_outputs": [
                f"{revision}.md",
                f"{revision}_report.md",
                f"{revision}.json",
                f"{revision}.prompt.json",
                f"{revision}.agent_tasks.md",
                f"{revision}.agent_completion.json",
            ],
            "core_managed_outputs": [f"{revision}.prompt.json", f"{revision}.agent_tasks.md"],
            "hard_constraints": [
                "The main creative Agent must execute the revision personally; subagents cannot write or polish prose.",
                "Every blocking issue, warning, revision action, style deviation, budget gap, reader-contract gap, and rhythm/bridge gap must map to an observable prose change or remain explicitly blocking.",
                "The revised deliverable body must differ from the exact source candidate; changing only reports or manifests is forbidden.",
                "The revision remains a candidate and must receive a fresh exact-candidate AgentReview before promotion.",
                "When the review requires a human/delegated direction, follow the matching exact-candidate decision in workflow/studio/user_directions.md and the review JSON. Do not alter canon or character assets from this prose task.",
            ],
            "style_constraints": [
                "Apply semantic anti-evasion revision rather than regex cleanup.",
                "Do not replace a banned contrast or transition with a cosmetic synonym.",
            ],
            "validation_gates": [
                "revision candidate and provenance files exist",
                "revision candidate differs from source sha256",
                "revision manifest records applied actions and ready_for_review=false",
                "revision sidecar completion marker exists",
            ],
            "next_allowed_states": ["candidate-review"],
        },
        "candidate-human-decision": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.scene-development.cross-asset-alignment.v1",
            "command": "",
            "source_paths": [scene_rel, revision_source, f"{review}.json", f"{review}.md"],
            "context_trace": context_trace,
            "expected_outputs": [],
            "hard_constraints": [
                "Do not revise prose or change a canon/character asset before this exact candidate receives a recorded decision.",
                "Choose align_prose_to_formal_asset only when the existing formal asset should win; choose hold_for_asset_revision when the asset itself must be revised through its formal route.",
                "The decision must be bound to this scene_id and candidate_sha256. Generic revision notes do not satisfy this gate.",
            ],
            "style_constraints": [],
            "validation_gates": ["matching human or delegated revision direction is recorded for the exact candidate sha256"],
            "next_allowed_states": ["candidate-revision"],
        },
        "agent-review-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.agent-review.complete.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{review}.agent_tasks.md", f"{candidate}.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{review}.json", f"{review}.md", f"{review}.agent_completion.json"],
            "hard_constraints": ["Complete AgentReview sidecar only after writing JSON/Markdown review for the exact candidate."],
            "style_constraints": ["Medium+ Style Lint findings are blocking unless revised and re-reviewed."],
            "validation_gates": ["AgentReview completion marker exists"],
            "next_allowed_states": ["promotion-manifest"],
        },
        "promotion-manifest": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": (
                f"python -m literary_engineering_studio_engine promote-candidate <project> --scene {scene_rel} "
                f"--candidate {candidate_markdown}"
                + (" --overwrite" if (root / "drafts" / "scenes" / f"{scene_id}.md").exists() else "")
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        candidate_markdown,
                        f"{candidate}.json",
                        f"{candidate}.prompt.json",
                        f"{candidate}.agent_tasks.md",
                        f"{candidate}.agent_completion.json",
                        f"{review}.json",
                        f"{review}.md",
                        f"{review}.agent_tasks.md",
                        f"{review}.agent_completion.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"drafts/promotions/{scene_id}_promotion.json", f"drafts/promotions/{scene_id}_promotion.md", f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Do not use --allow-unreviewed or --allow-review-notes."],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "promoted-draft": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.scene-development.promote.v1",
            "command": (
                f"python -m literary_engineering_studio_engine promote-candidate <project> --scene {scene_rel} "
                f"--candidate {candidate_markdown}"
                + (" --overwrite" if (root / "drafts" / "scenes" / f"{scene_id}.md").exists() else "")
            ),
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        candidate_markdown,
                        f"{candidate}.json",
                        f"{candidate}.prompt.json",
                        f"{candidate}.agent_tasks.md",
                        f"{candidate}.agent_completion.json",
                        f"{review}.json",
                        f"{review}.md",
                        f"{review}.agent_tasks.md",
                        f"{review}.agent_completion.json",
                    ]
                )
            ),
            "context_trace": context_trace,
            "expected_outputs": [f"drafts/scenes/{scene_id}.md"],
            "hard_constraints": ["Promoted draft must come from promote-candidate, not manual copy."],
            "style_constraints": [],
            "validation_gates": ["promoted draft exists"],
            "next_allowed_states": ["static-review"],
        },
        "static-review": {
            "task_type": "deterministic-review",
            "prompt_asset_id": "route.scene-development.static-review.v1",
            "command": f"python -m literary_engineering_studio_engine review-scene <project> drafts/scenes/{scene_id}.md",
            "source_paths": [*scene_runtime_sources, f"drafts/scenes/{scene_id}.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"reviews/{scene_id}-review.md"],
            "hard_constraints": [
                "Run deterministic static review on the exact promoted draft and record its honest conclusion.",
                "A non-pass static verdict is a valid completed task and must route into static-revision rather than rerunning the same unchanged review.",
            ],
            "style_constraints": ["Apply punctuation and Style Lint concerns surfaced by review."],
            "validation_gates": ["static review conclusion is recorded for exact promoted draft"],
            "next_allowed_states": ["static-revision", "state-patch-json"],
        },
        "static-revision": {
            "task_type": "main-platform-agent-prose-revision",
            "prompt_asset_id": "route.scene-development.revision.v1",
            "command": f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} --draft {revision_source} --review reviews/{scene_id}-review.md",
            "source_paths": list(
                dict.fromkeys(
                    [
                        *scene_runtime_sources,
                        revision_source,
                        f"reviews/{scene_id}-review.md",
                    ]
                )
            ),
            "context_trace": context_trace,
            "candidate": f"{revision}.md",
            "revision_source": revision_source,
            "expected_outputs": [
                f"{revision}.md",
                f"{revision}_report.md",
                f"{revision}.json",
                f"{revision}.prompt.json",
                f"{revision}.agent_tasks.md",
                f"{revision}.agent_completion.json",
            ],
            "core_managed_outputs": [f"{revision}.prompt.json", f"{revision}.agent_tasks.md"],
            "hard_constraints": [
                "The main creative Agent must revise the prose personally against every static review finding.",
                "The revised body must differ from the promoted draft and remain a candidate.",
                "After revision, run fresh exact-candidate AgentReview, promotion, and static review; do not edit the promoted draft in place.",
            ],
            "style_constraints": ["Apply semantic repairs; never use regex cleanup or cosmetic transition substitution."],
            "validation_gates": [
                "revision candidate differs from promoted draft sha256",
                "revision provenance and completion files exist",
                "revision manifest records applied actions and ready_for_review=false",
            ],
            "next_allowed_states": ["candidate-review"],
        },
        "state-patch-json": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.scene-development.state-evolve.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine state-evolve <project> --scene {scene_rel} --agent-tasks",
            "source_paths": [*scene_runtime_sources, f"drafts/scenes/{scene_id}.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{state_patch}.md", f"{state_patch}.json", f"{state_patch}.agent_tasks.md"],
            "hard_constraints": ["State patch is candidate material until reviewed and approved."],
            "style_constraints": [],
            "validation_gates": ["state patch JSON exists", "state-evolve sidecar exists"],
            "next_allowed_states": ["state-agent-task"],
        },
        "state-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.state-evolve.execute.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{state_patch}.md", f"{state_patch}.json", f"{state_patch}.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{state_patch}.agent_completion.json"],
            "hard_constraints": ["Review state patch consequences and complete the marker; do not apply state without approval."],
            "style_constraints": [],
            "validation_gates": ["state-evolve sidecar completion marker exists"],
            "next_allowed_states": ["canon-patch-json", "ready"],
        },
        "canon-patch-json": {
            "task_type": "deterministic-cli-plus-platform-review",
            "prompt_asset_id": "route.scene-development.canon-evolve.v1",
            "command": f"python -m literary_engineering_studio_engine canon-evolve <project> --scene {scene_rel}",
            "source_paths": [
                *scene_runtime_sources,
                f"drafts/scenes/{scene_id}.md",
                f"drafts/promotions/{scene_id}_promotion.json",
                f"{review}.json",
                f"{state_patch}.json",
                f"{state_patch}.agent_tasks.md",
                f"{state_patch}.agent_completion.json",
            ],
            "context_trace": context_trace,
            "expected_outputs": [f"{canon_patch}.md", f"{canon_patch}.json", f"{canon_patch}.agent_tasks.md"],
            "hard_constraints": [
                "Canon writeback is a candidate-only judgment after state-evolve; it must not directly modify canon files.",
                "If no durable world fact changed, the platform agent must write no_canon_change_reason instead of silently skipping.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon patch/no-change JSON exists", "canon-evolve sidecar exists when required"],
            "next_allowed_states": ["canon-agent-task"],
        },
        "canon-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.scene-development.canon-evolve.v1",
            "command": "",
            "source_paths": [scene_rel, context, context_trace, f"{canon_patch}.md", f"{canon_patch}.json", f"{canon_patch}.agent_tasks.md"],
            "context_trace": context_trace,
            "expected_outputs": [f"{canon_patch}.agent_completion.json"],
            "hard_constraints": [
                "Complete canon-evolve sidecar only after writing either a candidate canon patch or an explicit no-change rationale.",
                "Do not apply canon; promotion to canon remains a separate review/approval route.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon-evolve sidecar completion marker exists"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.scene-development.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "context_trace": context_trace,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing formal gate."],
        "style_constraints": [],
        "validation_gates": ["route-specific gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _longform_blueprint_for_state(root: Path, current_state: str, next_action: str) -> dict[str, object]:
    project_text = _read_text(root / "project.yaml")
    target_words = _project_int(project_text, "target_length") or _project_int(project_text, "target_words") or 100000
    volumes = _project_int(project_text, "volumes")
    genre = _project_scalar(project_text, "genre")
    command = f"python -m literary_engineering_studio_engine word-budget <project> --target-words {target_words}"
    if volumes:
        command += f" --volumes {volumes}"
    if genre:
        command += f" --genre {genre}"
    common_sources = ["project.yaml", "plot/outline.md", "scenes/"]
    table: dict[str, dict[str, object]] = {
        "word-budget-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.word-budget.prepare.v1",
            "command": command,
            "source_paths": common_sources,
            "expected_outputs": [
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
                "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
                "plot/chapter_obligations/chapter_obligations.agent_tasks.md",
            ],
            "hard_constraints": [
                "Run word-budget / longform-budget before bulk outline or scene generation.",
                "Inspect both emitted platform-agent sidecars; this task is only the deterministic budget scaffold.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word_budget.json exists", "word budget schema is valid", "budget, scene inventory, and chapter obligation sidecars exist"],
            "next_allowed_states": ["budget-agent-task"],
        },
        "budget-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.budget-expansion.execute.v1",
            "command": "",
            "source_paths": [
                "project.yaml",
                "plot/outline.md",
                "plot/word_budget/word_budget.md",
                "plot/word_budget/word_budget.json",
                "plot/word_budget/word_budget.agent_tasks.md",
            ],
            "expected_outputs": [
                "plot/candidates/outlines/word_budget_expansion.md",
                "reviews/word_budget/word_budget_review.md",
                "plot/word_budget/word_budget.agent_completion.json",
            ],
            "hard_constraints": [
                "Read word_budget.agent_tasks.md and write the budgeted outline candidate plus review.",
                "Judge whether the narrative inventory can support target length; do not solve shortfall by padding scenes.",
                "Keep expanded outline as candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["budget sidecar completion marker exists", "budgeted outline candidate exists", "word-budget review conclusion is recorded"],
            "next_allowed_states": ["budget-review", "scene-inventory-agent-task"],
        },
        "budget-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.budget-review.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/candidates/outlines/word_budget_expansion.md",
                "reviews/word_budget/word_budget_review.md",
            ],
            "expected_outputs": ["plot/candidates/outlines/word_budget_expansion.md", "reviews/word_budget/word_budget_review.md"],
            "repair_targets": ["plot/candidates/outlines/word_budget_expansion.md"],
            "hard_constraints": [
                "Revise the budgeted outline candidate against every review finding; changing only the conclusion is forbidden.",
                "The review conclusion must be pass before scene inventory planning is treated as formal.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["word-budget review conclusion is pass"],
            "next_allowed_states": ["scene-inventory-agent-task"],
        },
        "scene-inventory-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.scene-inventory.execute.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/word_budget/scene_inventory_expansion.agent_tasks.md",
                "plot/candidates/outlines/word_budget_expansion.md",
            ],
            "expected_outputs": [
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "reviews/word_budget/scene_inventory_review.md",
                "plot/word_budget/scene_inventory_expansion.agent_completion.json",
            ],
            "hard_constraints": [
                "Read scene_inventory_expansion.agent_tasks.md and create budgeted scene inventory candidates.",
                "Each added scene candidate needs target Chinese-content characters, function, participants, conflict, information release, consequence, and setup/payoff role.",
                "Scene inventory remains candidate material until review and user approval.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory sidecar completion marker exists", "scene inventory candidate exists", "scene inventory review conclusion is recorded"],
            "next_allowed_states": ["scene-inventory-review"],
        },
        "scene-inventory-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.scene-inventory-review.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "reviews/word_budget/scene_inventory_review.md",
            ],
            "expected_outputs": ["plot/candidates/scenes/word_budget_scene_inventory.md", "reviews/word_budget/scene_inventory_review.md"],
            "repair_targets": ["plot/candidates/scenes/word_budget_scene_inventory.md"],
            "hard_constraints": [
                "Revise the scene inventory candidate against every review finding; changing only the conclusion is forbidden.",
                "The scene inventory review conclusion must be pass before longform-planning is ready.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["scene inventory review conclusion is pass"],
            "next_allowed_states": ["chapter-obligation-agent-task"],
        },
        "chapter-obligation-agent-task": {
            "task_type": "platform-agent-judgment",
            "prompt_asset_id": "route.longform-planning.chapter-obligation.execute.v1",
            "command": "",
            "source_paths": [
                "project.yaml",
                "plot/outline.md",
                "plot/word_budget/word_budget.json",
                "plot/chapter_obligations/chapter_obligations.agent_tasks.md",
                "plot/candidates/scenes/word_budget_scene_inventory.md",
            ],
            "expected_outputs": [
                "plot/candidates/chapters/chapter_obligation_plan.md",
                "reviews/word_budget/chapter_obligation_review.md",
                "plot/chapter_obligations/chapter_obligations.agent_completion.json",
            ],
            "hard_constraints": [
                "Read chapter_obligations.agent_tasks.md and build a chapter-level promise/payoff plan.",
                "Each chapter must map target Chinese-content characters to reader questions, promised rewards, withheld information, payoff/delay, and anti-summary requirements.",
                "Per-scene chapter-obligation JSON files remain platform-agent contracts; create them with chapter-obligation before scene prose generation.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["chapter obligation sidecar completion marker exists", "chapter obligation plan candidate exists", "chapter obligation review conclusion is recorded"],
            "next_allowed_states": ["chapter-obligation-review"],
        },
        "chapter-obligation-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.longform-planning.chapter-obligation-review.v1",
            "command": "",
            "source_paths": [
                "plot/word_budget/word_budget.json",
                "plot/chapter_obligations/chapter_obligations.agent_tasks.md",
                "plot/candidates/chapters/chapter_obligation_plan.md",
                "reviews/word_budget/chapter_obligation_review.md",
            ],
            "expected_outputs": ["plot/candidates/chapters/chapter_obligation_plan.md", "reviews/word_budget/chapter_obligation_review.md"],
            "repair_targets": ["plot/candidates/chapters/chapter_obligation_plan.md"],
            "hard_constraints": [
                "Revise the chapter obligation plan against every review finding; changing only the conclusion is forbidden.",
                "The chapter obligation review conclusion must be pass before longform-planning is ready.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["chapter obligation review conclusion is pass"],
            "next_allowed_states": ["planning-materialization"],
        },
        "planning-materialization": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.longform-planning.materialize.v1",
            "command": "python -m literary_engineering_studio_engine materialize-longform-plan <project>",
            "source_paths": [
                "project.yaml",
                "plot/word_budget/word_budget.json",
                "plot/candidates/outlines/word_budget_expansion.md",
                "plot/candidates/scenes/word_budget_scene_inventory.md",
                "plot/candidates/chapters/chapter_obligation_plan.md",
                "reviews/word_budget/word_budget_review.md",
                "reviews/word_budget/scene_inventory_review.md",
                "reviews/word_budget/chapter_obligation_review.md",
                "scenes/scene_0001.yaml",
            ],
            "expected_outputs": planned_longform_outputs(root),
            "hard_constraints": [
                "Materialize only after the budget, scene inventory, and chapter obligation reviews all pass.",
                "Convert the reviewed candidate inventory into formal scene contracts; do not invent or omit scenes in this deterministic step.",
                "Never overwrite a scene that already contains formal development evidence.",
            ],
            "style_constraints": [],
            "word_count_target": target_words,
            "validation_gates": ["materialization manifest is current", "formal outline exists", "all budgeted formal scene YAML files exist"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.longform-planning.repair.v1",
        "command": next_action,
        "source_paths": common_sources,
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing longform-planning gate."],
        "style_constraints": [],
        "word_count_target": target_words,
        "validation_gates": ["longform-planning gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _source_ingest_blueprint_for_state(root: Path, work_id: str, import_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    manifest_path = root / import_dir / "source_manifest.json"
    manifest = _read_json(manifest_path)
    candidate_outputs = _source_candidate_outputs_from_manifest(manifest, work_id)
    task_path = f"{import_dir}/extract_project_files.agent_tasks.md"
    completion = f"{import_dir}/extract_project_files.agent_completion.json"
    report = f"{import_dir}/source_ingest.md"
    chunks = [str(item.get("path") or "") for item in manifest.get("chunks", []) if isinstance(item, dict)]
    candidate_values = list(candidate_outputs.values())
    review = candidate_outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
    table: dict[str, dict[str, object]] = {
        "source-manifest": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.source-ingest.import.v1",
            "command": "python -m literary_engineering_studio_engine source-ingest <project> --source <source> --title <title> --work-id <work-id>",
            "source_paths": ["project.yaml"],
            "expected_outputs": [f"{import_dir}/source_manifest.json", report, task_path],
            "hard_constraints": [
                "Run source-ingest with explicit source/text/title/work-id when starting a new import.",
                "If repairing an invalid manifest, preserve source evidence and candidate output paths.",
            ],
            "style_constraints": [],
            "validation_gates": ["source manifest exists", "source ingest report exists", "extraction sidecar exists", "source_manifest schema is valid"],
            "next_allowed_states": ["extraction-agent-task"],
        },
        "extraction-agent-task": {
            "task_type": "platform-agent-extraction",
            "prompt_asset_id": "route.source-ingest.extract-project-files.v1",
            "command": "",
            "source_paths": [f"{import_dir}/source_manifest.json", report, task_path, *chunks],
            "expected_outputs": [*candidate_values, completion],
            "hard_constraints": [
                "Read extract_project_files.agent_tasks.md and all source chunks before writing extracted candidates.",
                "Every extracted claim must include evidence_refs, confidence, unknowns, and contradiction notes when relevant.",
                "Write only candidate assets and source-ingest review; do not overwrite confirmed project files.",
            ],
            "style_constraints": [
                "For style notes from non-public-domain or unauthorized sources, abstract high-level craft features only.",
            ],
            "validation_gates": ["extraction sidecar completion marker exists", "all candidate outputs exist"],
            "next_allowed_states": ["extraction-review"],
        },
        "extraction-review": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.source-ingest.extraction-review.v1",
            "command": "",
            "source_paths": [f"{import_dir}/source_manifest.json", *chunks, *[item for item in candidate_values if item != review], review],
            "expected_outputs": [*[item for item in candidate_values if item != review], review],
            "repair_targets": [item for item in candidate_values if item != review],
            "hard_constraints": [
                "Revise the extracted candidate files against every review finding, then rewrite the review honestly.",
                "At least one declared extracted candidate must change; editing only the review conclusion is forbidden.",
                "The extraction review must be a clean pass before source-derived candidates are treated as route-ready.",
                "pass_with_notes, missing evidence, copied long passages, or direct canon writeback are blocking.",
            ],
            "style_constraints": [],
            "validation_gates": ["source-ingest extraction review conclusion is pass"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.source-ingest.repair.v1",
        "command": next_action,
        "source_paths": [f"{import_dir}/source_manifest.json", report],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing source-ingest gate."],
        "style_constraints": [],
        "validation_gates": ["source-ingest gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _style_engineering_blueprint_for_state(root: Path, profile_id: str, profile_dir: str, current_state: str, next_action: str) -> dict[str, object]:
    profile = f"{profile_dir}/style-profile.md"
    metrics = f"{profile_dir}/style_metrics.json"
    corpus_manifest = f"{profile_dir}/corpus_manifest.yaml"
    task = f"{profile_dir}/style_prompt.agent_tasks.md"
    prompt = f"{profile_dir}/style_prompt.md"
    agent_json = f"{profile_dir}/style_prompt.agent.json"
    completion = f"{profile_dir}/style_prompt.agent_completion.json"
    eval_dir = f"{profile_dir}/evaluation_results/formal"
    eval_candidate = f"{eval_dir}/platform_agent_candidate.md"
    eval_manifest = f"{eval_dir}/platform_agent_candidate.prompt.json"
    eval_task = f"{eval_dir}/platform_agent_candidate.agent_tasks.md"
    eval_completion = f"{eval_dir}/platform_agent_candidate.agent_completion.json"
    eval_json = f"{eval_dir}/style_eval_current.json"
    eval_report = f"{eval_dir}/style_eval_current.md"
    profile_path = _resolve_project_path(root, profile_dir)
    reference_path = next((path for path in sorted((profile_path / "corpus").glob("*.txt")) if path.is_file() and path.stat().st_size > 0), None)
    reference = _rel(reference_path, root) if reference_path is not None else ""
    table: dict[str, dict[str, object]] = {
        "style-profile": {
            "task_type": "deterministic-cli-or-repair",
            "prompt_asset_id": "route.style-engineering.profile.v1",
            "command": "python -m literary_engineering_studio_engine style-profile <corpus> --out-dir <profile-dir> --name <name>",
            "source_paths": [profile_dir],
            "expected_outputs": [profile, metrics],
            "hard_constraints": ["Compile or repair style-profile.md and style_metrics.json before prompt generation."],
            "style_constraints": [],
            "validation_gates": ["style profile exists", "style metrics exists"],
            "next_allowed_states": ["style-prompt-task-file"],
        },
        "style-prompt-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.prompt.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine style-prompt <project>/{profile_dir}",
            "source_paths": [profile, metrics, corpus_manifest],
            "expected_outputs": [task],
            "hard_constraints": [
                "Run style-prompt to create a platform-agent style prompt task sidecar.",
                "The command prepares the task; the platform agent still writes style_prompt.md and style_prompt.agent.json.",
            ],
            "style_constraints": [],
            "validation_gates": ["style_prompt.agent_tasks.md exists"],
            "next_allowed_states": ["style-prompt-agent-task"],
        },
        "style-prompt-agent-task": {
            "task_type": "platform-agent-style-prompt",
            "prompt_asset_id": "route.style-engineering.prompt.execute.v1",
            "command": "",
            "source_paths": [profile, metrics, corpus_manifest, task],
            "expected_outputs": [prompt, agent_json, completion],
            "hard_constraints": [
                "Read style_prompt.agent_tasks.md and write a detailed executable LLM-facing style prompt.",
                "style_prompt.md must be 500-2500 Chinese-content detail characters, counting Han characters and Chinese punctuation after Markdown scaffolding is stripped.",
                "style_prompt.md must include all required blocks: identity/boundary, mechanism, narrative distance, rhythm, punctuation, imagery, psychology/behavior, dialogue, AI-trace controls, forbidden tendencies, and self-check.",
            ],
            "style_constraints": [
                "Do not authorize mechanical contrast frames or dash variants as style.",
                "Public-domain or authorized corpora may support closer imitation; otherwise extract high-level craft only.",
            ],
            "validation_gates": ["style prompt sidecar completion marker exists", "style_prompt.md exists", "style_prompt.agent.json exists", "style prompt quality passes"],
            "next_allowed_states": ["style-prompt-quality", "style-eval-setup"],
        },
        "style-prompt-quality": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.style-engineering.prompt-quality.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json],
            "expected_outputs": [prompt, agent_json],
            "hard_constraints": [
                "Revise style_prompt.md until style_prompt_quality_report passes length and required-block checks.",
                "A vague prompt that only says the style is beautiful, restrained, literary, or advanced is not mountable.",
            ],
            "style_constraints": [],
            "validation_gates": ["style prompt quality passes"],
            "next_allowed_states": ["style-eval-setup"],
        },
        "style-eval-setup": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.style-engineering.eval.setup.v1",
            "command": "Import at least one authorized or public-domain UTF-8 corpus text into this style profile.",
            "source_paths": [profile, metrics, corpus_manifest],
            "expected_outputs": [],
            "hard_constraints": [
                "Do not fabricate a source corpus or claim authorization that the user did not provide.",
                "The formal evaluation reference must be a real non-empty UTF-8 text in the profile corpus.",
            ],
            "style_constraints": [],
            "validation_gates": ["authorized corpus reference exists"],
            "next_allowed_states": ["style-eval-task-file"],
        },
        "style-eval-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.eval.prepare.v1",
            "command": (
                f'python -m literary_engineering_studio_engine style-prompt-eval "<project>/{profile_dir}" '
                f'--reference "<project>/{reference}" --input "<project>/project.yaml" --mode blind-review '
                f'--out-dir "<project>/{eval_dir}"'
            ),
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml"],
            "expected_outputs": [eval_task],
            "hard_constraints": [
                "Prepare one concrete formal evaluation sidecar; no path placeholders may remain.",
                "Use the project direction as neutral content input and the corpus text only as evaluation reference.",
            ],
            "style_constraints": [],
            "validation_gates": ["formal style evaluation sidecar exists"],
            "next_allowed_states": ["style-eval-agent-task"],
        },
        "style-eval-agent-task": {
            "task_type": "platform-agent-evaluation",
            "prompt_asset_id": "route.style-engineering.eval.execute.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml", eval_task],
            "expected_outputs": [eval_candidate, eval_manifest, eval_completion],
            "hard_constraints": [
                "Generate the evaluation candidate from project.yaml under the mounted style prompt; do not copy the corpus reference.",
                "Write the exact candidate, prompt manifest, and completion marker declared by the sidecar.",
                "Do not self-score or label the candidate accepted; deterministic style-eval owns that decision.",
            ],
            "style_constraints": [],
            "validation_gates": ["evaluation sidecar completed", "candidate exists", "prompt manifest exists"],
            "next_allowed_states": ["style-eval-score-file"],
        },
        "style-eval-score-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.eval.score.v1",
            "command": (
                f'python -m literary_engineering_studio_engine style-eval "<project>/{profile_dir}" '
                f'--reference "<project>/{reference}" --candidate "<project>/{eval_candidate}" '
                f'--mode blind-review --out-dir "<project>/{eval_dir}"'
            ),
            "source_paths": [profile, metrics, prompt, reference, eval_candidate, eval_manifest],
            "expected_outputs": [eval_json, eval_report],
            "hard_constraints": [
                "Score the exact current candidate deterministically.",
                "Preserve candidate_sha256 and reference_sha256 in the current score JSON.",
            ],
            "style_constraints": [],
            "validation_gates": ["style score matches current candidate digest", "score and risk are recorded"],
            "next_allowed_states": ["style-eval-readiness", "style-eval-revision"],
        },
        "style-eval-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.style-engineering.eval.fix.v1",
            "command": "",
            "source_paths": [profile, metrics, prompt, agent_json, reference, "project.yaml", eval_candidate, eval_manifest, eval_json, eval_report],
            "expected_outputs": [prompt, agent_json, eval_candidate, eval_manifest, eval_completion],
            "repair_targets": [prompt, agent_json, eval_candidate, eval_manifest],
            "hard_constraints": [
                "Use deterministic score dimensions and risk evidence to revise both the style prompt and the generated candidate.",
                "Do not copy reference phrases to raise similarity and do not edit score files.",
                "Keep style_prompt.md within 500-2500 Chinese-content detail characters and preserve every required prompt block.",
                "Do not self-accept the revision; a fresh deterministic style-eval must score the new candidate digest.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "style prompt quality passes", "evaluation candidate is complete", "current score becomes stale until rerun"],
            "next_allowed_states": ["style-eval-score-file"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.style-engineering.repair.v1",
        "command": next_action,
        "source_paths": [profile_dir],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing style-engineering gate."],
        "style_constraints": [],
        "validation_gates": ["style-engineering gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _asset_blueprint_for_state(root: Path, candidate_id: str, asset_type: str, candidate: str, current_state: str, next_action: str) -> dict[str, object]:
    candidate_rel = candidate or ""
    candidate_path = _resolve_project_path(root, candidate_rel) if candidate_rel else root / "characters" / "candidates" / f"{candidate_id}.json"
    candidate_report = _rel(candidate_path.with_suffix(".md"), root)
    creation_task = _rel(candidate_path.with_suffix(".agent_tasks.md"), root)
    creation_completion = _rel(default_agent_completion_path(candidate_path.with_suffix(".agent_tasks.md")), root)
    review = f"reviews/assets/{candidate_id}_review.md"
    review_json = f"reviews/assets/{candidate_id}_review.json"
    review_task = f"reviews/assets/{candidate_id}_review.agent_tasks.md"
    review_completion = f"reviews/assets/{candidate_id}_review.agent_completion.json"
    promotion = f"workflow/asset_promotions/{candidate_id}_promotion.json"
    promotion_report = f"workflow/asset_promotions/{candidate_id}_promotion.md"
    group = _asset_promotion_group(asset_type)
    promoted_outputs = _asset_promoted_output_rels(root, candidate_path, asset_type)
    type_hint = asset_type or "<character|background-story|relationship|world|location|organization|outline|chapter-plan|scene-list>"
    compact_context = compact_asset_context_relpaths(root)
    creation_sources = [*compact_context, creation_task]
    review_sources = [candidate_rel, candidate_report, review_task, *compact_context]
    table: dict[str, dict[str, object]] = {
        "asset-intake": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.intake.v1",
            "command": "python -m literary_engineering_studio_engine seed-project-assets <project>",
            "source_paths": compact_context,
            "expected_outputs": [
                "canon/candidates/world_rules/world-foundation.agent_tasks.md",
                "characters/candidates/protagonist-foundation.agent_tasks.md",
            ],
            "hard_constraints": [
                "Run seed-project-assets to create stable world-foundation and protagonist-foundation platform-agent sidecars.",
                "This deterministic step creates task contracts only; it does not invent or promote canon and character facts.",
                "The platform agent must not write directly to confirmed canon, character files, outline, scenes, drafts, exports, or releases.",
            ],
            "style_constraints": [],
            "validation_gates": ["world and protagonist asset creation sidecars exist"],
            "next_allowed_states": ["asset-creation-agent-task"],
        },
        "asset-creation-agent-task": {
            "task_type": "platform-agent-asset-creation",
            "prompt_asset_id": "route.character-world-assets.create.v1",
            "command": "",
            "source_paths": creation_sources,
            "expected_outputs": [candidate_rel, candidate_report, creation_completion],
            "hard_constraints": [
                f"Read the asset creation sidecar and write a {type_hint} candidate asset, not a confirmed project file.",
                "Candidate JSON must satisfy its schema and include candidate_id, risks, source_paths, and promotion_notes.",
                "Character and background-story assets must preserve background_story as hidden behavioral causality, not exposition.",
            ],
            "style_constraints": ["Mounted style may inform names/tone but cannot override canon, world rules, or user constraints."],
            "validation_gates": ["asset creation sidecar completed", "candidate JSON exists", "candidate report exists", "candidate schema validates"],
            "next_allowed_states": ["asset-review-task-file"],
        },
        "asset-review-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.review.prepare.v1",
            "command": f"python -m literary_engineering_studio_engine review-candidate-asset <project> {candidate_rel}",
            "source_paths": [candidate_rel, candidate_report, *compact_context],
            "expected_outputs": [review_task],
            "hard_constraints": [
                "Run review-candidate-asset to create a formal platform-agent asset review sidecar.",
                "The command prepares the review task; the platform agent still performs the semantic review.",
            ],
            "style_constraints": [],
            "validation_gates": ["asset review sidecar exists"],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-review-agent-task": {
            "task_type": "platform-agent-asset-review",
            "prompt_asset_id": "route.character-world-assets.review.execute.v1",
            "command": "",
            "source_paths": review_sources,
            "expected_outputs": [review, review_json, review_completion],
            "hard_constraints": [
                "Review candidate asset against schema, canon, character logic, originality, hidden background-story policy, and promotion risk.",
                "Write JSON with status pass|failed|revise_required plus blocking_issues, warnings, revision_actions, and promotion_risks.",
                "Revision actions may modify only the current candidate and its report. Put dependencies on other characters, canon assets, scenes, or routes into warnings/promotion_risks instead of blocking this candidate.",
                "Do not use review as approval. A clean review only permits asking the user whether to approve promotion.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "asset review sidecar completed",
                "review JSON exists",
                "review Markdown exists",
                "review status is recorded as pass|failed|revise_required",
            ],
            "next_allowed_states": ["asset-review-pass", "asset-approval"],
        },
        "asset-review-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.character-world-assets.review-fix.v1",
            "command": "",
            "source_paths": [candidate_rel, review, review_json],
            "expected_outputs": [candidate_rel, candidate_report, review, review_json, review_completion],
            "hard_constraints": [
                "Resolve every blocking issue and revision action in the candidate asset before asking for approval.",
                "Do not create files outside Allowed Outputs. If an old review action asks for another asset or route, preserve it as a follow-up warning/promotion risk and revise only candidate-local findings.",
                "Do not bury revise_required findings as harmless warnings.",
                "Do not self-pass the review that requested this revision and do not replace critical findings with a clean verdict.",
                "After revising the candidate and candidate report, preserve the previous findings as applied_revision_actions, set review status to recheck_required, and reset the review completion marker to recheck_required with expected_artifacts_checked=false.",
                "A fresh asset-review-agent-task must independently inspect the revised candidate before approval is possible.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "candidate schema validates",
                "candidate content changed from pre-revision sha256",
                "review status is recheck_required",
                "applied_revision_actions recorded",
                "review completion evidence reset for independent recheck",
            ],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-approval-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.character-world-assets.approval-fix.v1",
            "command": "",
            "source_paths": [candidate_rel, candidate_report, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": [candidate_rel, candidate_report, review, review_json, review_completion],
            "hard_constraints": [
                "Revise only the current candidate and its report against the latest matching approval decision rationale.",
                "A revise or reject approval is not permission to approve, promote, or edit confirmed project assets.",
                "After changing the candidate, record the approval rationale in applied_revision_actions, set the prior review to recheck_required, and reset its completion marker for independent review.",
                "Do not self-pass the revised candidate; a fresh review and a new approval bound to the new candidate digest are mandatory.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "candidate content changed from the approval-bound sha256",
                "candidate schema validates",
                "review status is recheck_required",
                "applied_revision_actions record the approval rationale",
                "review completion evidence reset for independent recheck",
            ],
            "next_allowed_states": ["asset-review-agent-task"],
        },
        "asset-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.character-world-assets.approval.v1",
            "command": f"Ask the user whether to approve candidate `{candidate_id}` for promotion; record approve decision with run_id `{candidate_id}` through the platform approval mechanism.",
            "source_paths": [candidate_rel, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The executing Worker must not self-approve candidate promotion. Approval may come from the user or a separately identified Creative Steward under an active DelegationPolicy.",
                "If the user asks for revision or rejection, record that decision and do not promote.",
                "Approval must reference the candidate_id/run_id that promote-candidate-asset will use.",
            ],
            "style_constraints": [],
            "validation_gates": ["approve record exists for candidate_id"],
            "next_allowed_states": ["asset-promotion"],
        },
        "asset-promotion": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.character-world-assets.promote.v1",
            "command": f"python -m literary_engineering_studio_engine promote-candidate-asset <project> {candidate_rel} --group {group or '<group>'} --approval-run-id {candidate_id}",
            "source_paths": [candidate_rel, review, review_json, "workflow/approvals/index.jsonl"],
            "expected_outputs": [promotion, promotion_report, *promoted_outputs],
            "hard_constraints": [
                "Promote only after clean review and matching approve record.",
                "Do not use --allow-unapproved in formal Skill-host work.",
                "After promotion, run canon-lint or the relevant downstream route before relying on the new project facts.",
            ],
            "style_constraints": [],
            "validation_gates": ["promotion manifest exists", "allow_unapproved is false", "promotion outputs exist"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.character-world-assets.repair.v1",
        "command": next_action,
        "source_paths": [candidate_rel] if candidate_rel else ["project.yaml", "canon", "characters", "plot"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and repair the missing character/world asset gate."],
        "style_constraints": [],
        "validation_gates": ["character/world asset gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _project_review_repair_targets(root: Path, review_path: Path, fields: tuple[str, ...]) -> list[str]:
    if not review_path.is_file():
        return []
    payload = _read_json(review_path)
    allowed_prefixes = ("canon/", "characters/", "plot/", "scenes/", "drafts/candidates/")
    targets: list[str] = []
    for field in fields:
        items = payload.get(field) if isinstance(payload.get(field), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target_path") or item.get("target") or "").replace("\\", "/").strip()
            target = target.split("#", 1)[0]
            if (
                target
                and not Path(target).is_absolute()
                and ".." not in Path(target).parts
                and target.startswith(allowed_prefixes)
                and Path(target).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv"}
            ):
                targets.append(target)
    return _unique(targets)


def _review_audit_blueprint_for_state(
    root: Path,
    current_state: str,
    next_action: str,
    state: dict[str, object] | None = None,
) -> dict[str, object]:
    state = state or {}
    patch = str(state.get("patch") or "")
    patch_id = str(state.get("patch_id") or (Path(patch).stem if patch else "canon-patch"))
    patch_report = str(Path(patch).with_suffix(".md")).replace("\\", "/") if patch else ""
    patch_task = str(Path(patch).with_suffix(".agent_tasks.md")).replace("\\", "/") if patch else ""
    patch_completion = str(Path(patch).with_suffix(".agent_completion.json")).replace("\\", "/") if patch else ""
    canon_review = "reviews/agent/canon_review"
    committee = "reviews/agent/committee_project-final-audit"
    canon_repair_targets = _project_review_repair_targets(
        root,
        root / f"{canon_review}.json",
        ("blocking_issues", "warnings", "unresolved_facts", "timeline_risks", "recommendations"),
    )
    committee_repair_targets = _project_review_repair_targets(
        root,
        root / f"{committee}.json",
        ("action_items", "disagreements"),
    )
    table: dict[str, dict[str, object]] = {
        "canon-patch-revision": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.canon-patch.fix.v1",
            "command": "",
            "source_paths": [item for item in [patch, patch_report, patch_task, patch_completion, "workflow/approvals/index.jsonl", "canon", "scenes", "drafts/scenes"] if item],
            "expected_outputs": [item for item in [patch, patch_report, patch_completion] if item],
            "repair_targets": [item for item in [patch, patch_report] if item],
            "hard_constraints": [
                "Revise only the current canon patch candidate and report against the recorded approval or validation findings.",
                "Do not edit durable canon files and do not mark the patch applied.",
                "Keep canon_change=true only for cross-scene durable facts; every item must retain exact evidence, target_files, risk, and approval requirements.",
                "After a real content change, complete the canon-evolve marker and request a fresh content-bound decision.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon patch candidate changed", "canon patch schema is apply-ready", "canon-evolve completion is complete", "patch remains unapplied"],
            "next_allowed_states": ["canon-patch-approval"],
        },
        "canon-patch-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.review-audit.canon-patch.approval.v1",
            "command": f"Ask for a decision on canon patch `{patch_id}` and bind it to the current candidate SHA-256.",
            "source_paths": [item for item in [patch, patch_report, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The writing Worker must not self-approve its own canon patch.",
                "Record approve, revise, reject, or defer against the exact current patch digest.",
                f"The approval run_id must be `{patch_id}`.",
            ],
            "style_constraints": [],
            "validation_gates": ["a current-content canon patch decision is recorded"],
            "next_allowed_states": ["canon-patch-apply", "canon-patch-revision", "canon-patch-deferred"],
        },
        "canon-patch-deferred": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.review-audit.canon-patch.approval.v1",
            "command": f"Canon patch `{patch_id}` is deferred. Resume it from the decision panel when ready.",
            "source_paths": [item for item in [patch, patch_report, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": ["Do not silently apply or discard a deferred canon patch."],
            "style_constraints": [],
            "validation_gates": ["user or delegated steward explicitly resumes the deferred patch"],
            "next_allowed_states": ["canon-patch-apply", "canon-patch-revision"],
        },
        "canon-patch-apply": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-patch.apply.v1",
            "command": f"python -m literary_engineering_studio_engine canon-apply <project> --patch {patch} --approval-run-id {patch_id}",
            "source_paths": [item for item in [patch, patch_report, patch_completion, "workflow/approvals/index.jsonl"] if item],
            "expected_outputs": [
                patch,
                f"canon/applied/{patch_id}_apply.json",
                f"canon/applied/{patch_id}_apply.md",
                "canon/canon_change_log.md",
            ],
            "hard_constraints": [
                "Apply only the exact approved patch candidate.",
                "Do not use --allow-unapproved in formal operation.",
                "The apply manifest must preserve approval evidence and the pre-apply candidate digest.",
            ],
            "style_constraints": [],
            "validation_gates": ["patch status is applied", "apply manifest is valid", "approval digest matches applied candidate", "no approval bypass"],
            "next_allowed_states": ["canon-lint-file"],
        },
        "canon-lint-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-lint.v1",
            "command": "python -m literary_engineering_studio_engine canon-lint <project>",
            "source_paths": ["project.yaml", "canon", "characters", "plot", "scenes", "drafts/scenes"],
            "expected_outputs": ["reviews/canon_lint.md", "reviews/canon_lint.json"],
            "hard_constraints": [
                "Run canon-lint before any platform-agent project-level semantic review.",
                "Blocking canon-lint issues must be fixed or explicitly captured as candidate repair tasks before export.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon-lint report exists", "canon-lint JSON schema/status is usable", "blocking_count is 0"],
            "next_allowed_states": ["canon-review-task-file"],
        },
        "canon-review-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.canon-review.prepare.v1",
            "command": "python -m literary_engineering_studio_engine agent-canon-review <project>",
            "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", "canon", "characters", "plot", "scenes"],
            "expected_outputs": [f"{canon_review}.agent_tasks.md"],
            "hard_constraints": [
                "Run agent-canon-review only to create a platform-agent sidecar.",
                "The command prepares the task; the platform agent writes canon_review.v1 JSON/Markdown.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon review sidecar exists"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
        "canon-review-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.review-audit.canon-review.execute.v1",
            "command": "",
            "source_paths": ["reviews/canon_lint.md", "reviews/canon_lint.json", f"{canon_review}.agent_tasks.md", "canon", "characters", "plot", "scenes"],
            "expected_outputs": [f"{canon_review}.json", f"{canon_review}.md", f"{canon_review}.agent_completion.json"],
            "hard_constraints": [
                "Read canon lint, canon files, characters, scenes, plot, and write canon_review.v1.",
                "pass_with_notes is not a clean release gate; unresolved facts and timeline risks must become repair tasks or be resolved.",
                "A non-pass conclusion is a valid completed review. Every actionable finding must name one exact target_path under canon/, characters/, plot/, scenes/, or drafts/candidates/.",
                "Do not call local providers. The host platform agent is the reviewer.",
            ],
            "style_constraints": [],
            "validation_gates": ["canon review sidecar completed", "canon_review.v1 validates", "canon review conclusion is recorded"],
            "next_allowed_states": ["canon-review-pass", "longform-audit-file"],
        },
        "canon-review-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.canon-review.fix.v1",
            "command": "",
            "source_paths": [f"{canon_review}.json", f"{canon_review}.md", "reviews/canon_lint.json", *canon_repair_targets],
            "expected_outputs": [
                *canon_repair_targets,
                "reviews/canon_lint.md",
                "reviews/canon_lint.json",
                f"{canon_review}.json",
                f"{canon_review}.md",
                f"{canon_review}.agent_completion.json",
            ],
            "repair_targets": canon_repair_targets,
            "hard_constraints": [
                "Resolve every finding only in its declared target_path; do not touch files outside Allowed Outputs.",
                "Do not relabel unresolved findings as warnings to pass the gate.",
                "After repair run canon-lint in the sandbox, set canon review conclusion to recheck_required, and reset its completion marker for a fresh independent canon review.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "canon-lint passes", "canon review reset to recheck_required"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
        "longform-audit-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.longform-audit.v1",
            "command": "python -m literary_engineering_studio_engine longform-audit <project>",
            "source_paths": ["project.yaml", "plot/chapters", "scenes", "drafts/scenes", "reviews/agent", "plot/word_budget"],
            "expected_outputs": ["reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json", "plot/longform_graph.json"],
            "hard_constraints": [
                "Run longform-audit after canon review so the committee sees structural risks, word-budget gaps, and chapter readiness.",
                "Longform audit facts are evidence; the committee must still make semantic judgment.",
            ],
            "style_constraints": [],
            "validation_gates": ["longform audit JSON exists", "longform audit schema is valid", "longform graph exists"],
            "next_allowed_states": ["committee-task-file"],
        },
        "committee-task-file": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.review-audit.committee.prepare.v1",
            "command": "python -m literary_engineering_studio_engine agent-committee <project> --subject project-final-audit --source reviews/agent/canon_review.md",
            "source_paths": [f"{canon_review}.md", f"{canon_review}.json", "reviews/longform/longform_audit.md", "reviews/longform/longform_audit.json"],
            "expected_outputs": [f"{committee}.agent_tasks.md"],
            "hard_constraints": [
                "Run agent-committee only to create a platform-agent sidecar.",
                "Committee review must inspect canon review and longform audit; it cannot approve by vibe.",
            ],
            "style_constraints": [],
            "validation_gates": ["committee sidecar exists"],
            "next_allowed_states": ["committee-agent-task"],
        },
        "committee-agent-task": {
            "task_type": "platform-agent-review",
            "prompt_asset_id": "route.review-audit.committee.execute.v1",
            "command": "",
            "source_paths": [f"{committee}.agent_tasks.md", f"{canon_review}.json", f"{canon_review}.md", "reviews/longform/longform_audit.json", "reviews/longform/longform_audit.md"],
            "expected_outputs": [f"{committee}.json", f"{committee}.md", f"{committee}.agent_completion.json"],
            "hard_constraints": [
                "Act as a multi-perspective review committee: chief editor, character psychology, canon auditor, style auditor, readability, and anti-homogeneity.",
                "final_recommendation=approve is allowed only when no action_items or disagreements remain.",
                "approve_with_notes, revise, reject, action_items, or disagreements block export readiness.",
                "A non-approve recommendation is a valid completed committee review. Each action item or disagreement that requires repair must name an exact target_path.",
            ],
            "style_constraints": [],
            "validation_gates": ["committee sidecar completed", "committee_review.v1 validates", "final_recommendation is recorded"],
            "next_allowed_states": ["committee-pass"],
        },
        "committee-pass": {
            "task_type": "platform-agent-revision",
            "prompt_asset_id": "route.review-audit.committee.fix.v1",
            "command": "",
            "source_paths": [f"{committee}.json", f"{committee}.md", f"{canon_review}.json", "reviews/longform/longform_audit.json", *committee_repair_targets],
            "expected_outputs": [
                *committee_repair_targets,
                "reviews/canon_lint.md",
                "reviews/canon_lint.json",
                "reviews/longform/longform_audit.md",
                "reviews/longform/longform_audit.json",
                "plot/longform_graph.json",
                f"{canon_review}.json",
                f"{canon_review}.md",
                f"{canon_review}.agent_completion.json",
                f"{committee}.json",
                f"{committee}.md",
                f"{committee}.agent_completion.json",
            ],
            "repair_targets": committee_repair_targets,
            "hard_constraints": [
                "Resolve every committee action item and disagreement only in its declared target_path.",
                "Do not move to export-and-release on approve_with_notes.",
                "Rerun canon-lint and longform-audit after repair, then reset canon and committee completion evidence so both receive fresh independent review.",
            ],
            "style_constraints": [],
            "validation_gates": ["at least one declared repair target changed", "canon and committee reviews reset to recheck_required", "fresh deterministic audits exist"],
            "next_allowed_states": ["canon-review-agent-task"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.review-audit.repair.v1",
        "command": next_action,
        "source_paths": ["reviews", "canon", "characters", "plot", "scenes"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing review-and-audit gate."],
        "style_constraints": [],
        "validation_gates": ["review-and-audit gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _export_release_blueprint_for_state(root: Path, chapter_id: str, current_state: str, next_action: str) -> dict[str, object]:
    _ = root
    approval_run_id = f"release-{chapter_id}"
    release_dir = f"releases/{chapter_id}/formal-release"
    table: dict[str, dict[str, object]] = {
        "chapter-workspace": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.chapter-workspace.v1",
            "command": f"python -m literary_engineering_studio_engine chapter-workspace <project> --chapter-id {chapter_id}",
            "source_paths": ["scenes", "drafts/scenes", "reviews", "reviews/agent", "branches", "drafts/compositions", "characters/state_patches"],
            "expected_outputs": [f"drafts/chapters/{chapter_id}.md", f"plot/chapters/{chapter_id}.json"],
            "hard_constraints": [
                "Rebuild or verify chapter workspace immediately before export.",
                "Every scene must be ready with formal flow gates, static review pass, exact-candidate AgentReview pass, and no unresolved notes.",
            ],
            "style_constraints": ["Final body extraction must exclude workflow traces, canon notes, state patches, review notes, and scene ids."],
            "validation_gates": ["chapter workspace exists", "blocked_count is 0", "ready_count > 0"],
            "next_allowed_states": ["export-package"],
        },
        "export-package": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.package.v1",
            "command": f"python -m literary_engineering_studio_engine export-package <project> --chapter-id {chapter_id} --formats md,docx",
            "source_paths": [f"plot/chapters/{chapter_id}.json", f"drafts/chapters/{chapter_id}.md", "drafts/scenes", "reviews/agent"],
            "expected_outputs": [
                f"exports/{chapter_id}/export_manifest.json",
                f"exports/{chapter_id}/{chapter_id}_novel.md",
                f"exports/{chapter_id}/{chapter_id}_screenplay.md",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.md",
                f"exports/{chapter_id}/{chapter_id}_novel.docx",
                f"exports/{chapter_id}/{chapter_id}_novel.layout.json",
                f"exports/{chapter_id}/{chapter_id}_novel.inspection.json",
                f"exports/{chapter_id}/{chapter_id}_screenplay.docx",
                f"exports/{chapter_id}/{chapter_id}_screenplay.layout.json",
                f"exports/{chapter_id}/{chapter_id}_screenplay.inspection.json",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.docx",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.layout.json",
                f"exports/{chapter_id}/{chapter_id}_video_prompt_pack.inspection.json",
            ],
            "hard_constraints": [
                "Do not use --include-blocked in formal Skill-host work.",
                "Export manifest must have zero skipped scenes and include_blocked=false.",
                "Final outputs must filter scene ids, canon notes, review notes, state patches, AGENT_TASK markers, and writeback candidates.",
            ],
            "style_constraints": ["Normalize punctuation for delivery; maintain Chinese quote standard and no raw workbench traces."],
            "validation_gates": ["export manifest exists", "skipped_scenes is empty", "include_blocked is false", "delivery outputs exist"],
            "next_allowed_states": ["release-approval"],
        },
        "release-approval": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.export-release.approval.v1",
            "command": f"Ask the user whether to approve chapter `{chapter_id}` for release; record approve decision with run_id `{approval_run_id}`.",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", f"exports/{chapter_id}/{chapter_id}_novel.md", "workflow/approvals/index.jsonl"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "The executing Worker must not self-approve release publication. Approval may come from the user or a separately identified Creative Steward when the active DelegationPolicy explicitly delegates release.",
                "If the user requests revision or rejection, record that decision and return to the relevant review/export task.",
                f"Approval run_id must be `{approval_run_id}` so publish-chapter can verify it.",
            ],
            "style_constraints": [],
            "validation_gates": [f"approve record exists for {approval_run_id}"],
            "next_allowed_states": ["publish-release"],
        },
        "release-revision-required": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.export-release.approval.v1",
            "command": f"Release `{chapter_id}` was rejected or returned for revision. Select the affected scene-development work before rebuilding export.",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", f"drafts/chapters/{chapter_id}.md", "workflow/approvals/index.jsonl", "reviews/agent"],
            "expected_outputs": ["workflow/approvals/index.jsonl"],
            "hard_constraints": [
                "Do not regenerate the same export and ask for the same approval again.",
                "Return requested prose changes through scene revision, exact-candidate AgentReview, promotion, and chapter workspace before a fresh export.",
                "A new release decision must bind to the rebuilt export fingerprint.",
            ],
            "style_constraints": [],
            "validation_gates": ["affected scene revisions are explicitly selected before workflow resumes"],
            "next_allowed_states": ["chapter-workspace"],
        },
        "publish-release": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.export-release.publish.v1",
            "command": f"python -m literary_engineering_studio_engine publish-chapter <project> --chapter-id {chapter_id} --release-id formal-release --approval-run-id {approval_run_id} --export-formats md,docx",
            "source_paths": [f"exports/{chapter_id}/export_manifest.json", "workflow/approvals/index.jsonl", "reviews/canon_lint.json", f"plot/chapters/{chapter_id}.json"],
            "expected_outputs": [
                f"{release_dir}/publish_manifest.json",
                f"{release_dir}/release_notes.md",
                f"{release_dir}/rollback.md",
                f"{release_dir}/{chapter_id}_novel.md",
                f"{release_dir}/{chapter_id}_screenplay.md",
                f"{release_dir}/{chapter_id}_video_prompt_pack.md",
                f"{release_dir}/source_export_manifest.json",
                f"{release_dir}/{chapter_id}_novel.docx",
                f"{release_dir}/{chapter_id}_screenplay.docx",
                f"{release_dir}/{chapter_id}_video_prompt_pack.docx",
                f"releases/{chapter_id}/latest.json",
                "reviews/canon_lint.md",
                "reviews/canon_lint.json",
            ],
            "hard_constraints": [
                "Do not use --allow-unapproved in formal Skill-host work.",
                "Published manifest must have status=published and copied delivery outputs.",
                "If the release directory already exists, do not overwrite casually; inspect latest and ask the user before replacing.",
            ],
            "style_constraints": [],
            "validation_gates": ["publish manifest exists", "status is published", "latest.json points to release", "no approval bypass"],
            "next_allowed_states": ["ready"],
        },
    }
    default = {
        "task_type": "manual-route-repair",
        "prompt_asset_id": "route.export-release.repair.v1",
        "command": next_action,
        "source_paths": [f"plot/chapters/{chapter_id}.json", f"exports/{chapter_id}", f"releases/{chapter_id}"],
        "expected_outputs": [],
        "hard_constraints": [next_action or "Inspect workflow-state and route-audit, then repair the missing export-and-release gate."],
        "style_constraints": [],
        "validation_gates": ["export-and-release gate resolved"],
        "next_allowed_states": [],
    }
    return table.get(current_state, default)


def _render_task_markdown(task: dict[str, object], root: Path) -> str:
    task_id = str(task.get("task_id") or "")
    human_required = str(task.get("execution_policy") or "") == "human-required"
    completion = default_agent_completion_path(_task_markdown_path(root, task_id))
    lines = [
        f"# CLI 中介平台 Agent 任务：{task_id}",
        "",
        "本文件由 `task-next` / `task-open` 生成，代表一个正式项目操作任务。"
        if not human_required
        else "本文件由 `task-next` / `task-open` 生成，代表一个需要明确记录的用户决策边界。",
        "用户可以继续与平台 Agent 自然对话；但本任务涉及的正式产物必须通过 CLI 提交和完成。"
        if not human_required
        else "请在 Studio 决策界面记录选择；此任务不要求 Agent 创建文件，也不允许 Agent 替用户做出选择。",
        "",
        "## Task Metadata",
        "",
        f"- task_id: `{task_id}`",
        f"- route: `{task.get('route', '')}`",
        f"- scene_id: `{task.get('scene_id', '')}`",
        f"- current_state: `{task.get('current_state', '')}`",
        f"- task_type: `{task.get('task_type', '')}`",
        f"- prompt_asset_id: `{task.get('prompt_asset_id', '')}`",
        f"- execution_policy: `{task.get('execution_policy', '')}`",
        f"- agent_role: `{task.get('agent_role', '')}`",
        f"- context_trace: `{task.get('context_trace', '') or 'n/a'}`",
        f"- status: `{task.get('status', '')}`",
        *([] if human_required else [f"- completion_marker: `{_rel(completion, root)}`"]),
        "",
        *_prompt_asset_lines(str(task.get("prompt_asset_id") or "")),
        "",
        "## Required Reading",
        "",
    ]
    for item in task.get("required_reading") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Source Artifacts", ""])
    source_paths = list(task.get("source_paths") or [])
    if source_paths:
        for item in source_paths:
            lines.append(f"- `{item}`")
    else:
        lines.append("- 无。")
    lines.extend(["", "## Command", ""])
    command = str(task.get("command") or "").strip()
    if human_required:
        lines.append("- No command. Record the offered decision through the Studio interface.")
    elif command:
        lines.extend(["```powershell", command, "```"])
    else:
        lines.append("- 本任务主要由平台 Agent 读取 source artifacts 后写出判断或创作产物。")
    lines.extend(["", "## Hard Constraints", ""])
    for item in task.get("hard_constraints") or []:
        lines.append(f"- {item}")
    style_constraints = list(task.get("style_constraints") or [])
    if style_constraints:
        lines.extend(["", "## Style Constraints", ""])
        for item in style_constraints:
            lines.append(f"- {item}")
    lines.extend(["", "## Expected Outputs", ""])
    expected_outputs = list(task.get("expected_outputs") or [])
    if expected_outputs:
        for item in expected_outputs:
            lines.append(f"- 创建或覆盖 `{item}`")
    elif human_required:
        lines.append("- No file output. Studio records the decision as formal evidence.")
    else:
        lines.append("- 本任务没有固定文件输出；完成前仍需通过 `task-submit` 记录证据。")
    core_managed_outputs = list(task.get("core_managed_outputs") or [])
    if core_managed_outputs:
        lines.extend(["", "## CLI Protected Outputs", ""])
        lines.append("以下文件由本任务的 CLI Command 生成。平台 Agent 必须读取它们，但不得创建、覆盖、删除或用手写版本替代它们。")
        for item in core_managed_outputs:
            lines.append(f"- 只读 `{item}`")
    lines.extend(["", "## Validation Gates", ""])
    for item in task.get("validation_gates") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Forbidden Shortcuts", ""])
    for item in task.get("forbidden_shortcuts") or []:
        lines.append(f"- {item}")
    if human_required:
        lines.extend(
            [
                "",
                "## Human Decision Boundary",
                "",
                "This is a recorded human decision, not an Agent execution task. Do not create, revise, submit, or complete files from this task package.",
                "Record exactly one offered option through the Studio decision interface. The recorded choice must retain the task target and exact candidate SHA-256. Then request the next task again.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Agent Execution",
                "",
                "[AGENT_TASK: 读取本任务的 Required Reading 和 Source Artifacts。按 Command 或 Hard Constraints 完成产物。完成后先运行 task-submit 记录你写出的产物，再运行 task-complete。不得只手写文件后跳到下一步。]",
                "",
                "推荐提交命令：",
                "",
                "```powershell",
                str(task.get("submission_command") or ""),
                "```",
                "",
                "推荐完成命令：",
                "",
                "```powershell",
                str(task.get("completion_command") or ""),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _prompt_asset_lines(prompt_asset_id: str) -> list[str]:
    lines = ["## Prompt Asset", ""]
    if not prompt_asset_id:
        lines.append("- missing prompt_asset_id")
        return lines
    try:
        preview = resolve_prompt_asset(prompt_asset_id)
    except FileNotFoundError as exc:
        lines.append(f"- registry_error: `{exc}`")
        return lines
    if preview.asset is None:
        lines.append(f"- requested_id: `{prompt_asset_id}`")
        lines.append("- status: `missing`")
        lines.append("- action: run `prompt-registry-validate` before treating this task package as complete.")
        return lines

    asset = preview.asset
    lines.extend(
        [
            f"- requested_id: `{prompt_asset_id}`",
            f"- resolved_id: `{asset.prompt_asset_id}`",
            f"- match: `{asset.match}`",
            f"- version: `{asset.version}`",
            f"- title: {asset.title}",
        ]
    )
    prompt_sections = (
        ("required_inputs", "Required Inputs"),
        ("optional_inputs", "Optional Inputs"),
        ("context_groups", "Context Groups"),
        ("hard_constraints", "Hard Constraints"),
        ("style_constraints", "Style Constraints"),
        ("output_contract", "Output Contract"),
        ("review_requirements", "Review Requirements"),
        ("forbidden_shortcuts", "Forbidden Shortcuts"),
    )
    for field, title in prompt_sections:
        values = [str(item) for item in asset.metadata.get(field) or []]
        if not values and field in {"optional_inputs", "style_constraints"}:
            continue
        lines.extend(["", f"### Prompt {title}", ""])
        lines.extend(f"- {item}" for item in values)
    lines.extend(["", "### Prompt Body", "", asset.body.strip()])
    return lines


def _enrich_task_payload(task: dict[str, object]) -> dict[str, object]:
    enriched = dict(task)
    prompt_id = str(enriched.get("prompt_asset_id") or "").strip()
    if not prompt_id:
        raise ValueError("formal task is missing prompt_asset_id")
    preview = resolve_prompt_asset(prompt_id)
    if preview.asset is None:
        raise ValueError(f"formal task prompt asset is not registered: {prompt_id}")

    asset = preview.asset
    prompt_asset: dict[str, object] = {
        "requested_id": prompt_id,
        "resolved_id": asset.prompt_asset_id,
        "exact": preview.exact,
        "match": asset.match,
        "version": asset.version,
        "route": asset.route,
        "task_type": str(asset.metadata.get("task_type") or ""),
        "title": asset.title,
        "body": asset.body.strip(),
    }
    for field in PROMPT_METADATA_LIST_FIELDS:
        prompt_asset[field] = [str(item) for item in asset.metadata.get(field) or []]
    enriched["prompt_asset"] = prompt_asset

    expected_outputs = [str(item) for item in enriched.get("expected_outputs") or []]
    core_managed_outputs = {str(item) for item in enriched.get("core_managed_outputs") or []}
    present_contract_fields = EXPLICIT_TASK_CONTRACT_FIELDS & set(enriched)
    if present_contract_fields == EXPLICIT_TASK_CONTRACT_FIELDS:
        if str(enriched.get("execution_policy") or "") == "human-required":
            enriched["submission_command"] = ""
            enriched["completion_command"] = ""
        return enriched
    if present_contract_fields:
        missing = ", ".join(sorted(EXPLICIT_TASK_CONTRACT_FIELDS - present_contract_fields))
        raise ValueError(f"formal task has a partial explicit execution contract; missing: {missing}")

    task_type = str(enriched.get("task_type") or "").strip()
    try:
        execution_policy, agent_role = TASK_TYPE_EXECUTION[task_type]
    except KeyError as exc:
        raise ValueError(f"formal task has no explicit execution contract for task_type: {task_type}") from exc
    human_required = execution_policy == "human-required"
    human_reasons = [str(enriched.get("current_state") or "human-decision")] if human_required else []
    if execution_policy == "deterministic":
        capabilities = ["deterministic-command"]
    elif human_required:
        capabilities = []
    else:
        capabilities = ["read-task-sources"]
        if expected_outputs:
            capabilities.append("write-expected-outputs")

    enriched.update(
        {
            "execution_policy": execution_policy,
            "agent_role": agent_role,
            "human_gate": {
                "required": human_required,
                "reasons": human_reasons,
                "source": "task-registry",
            },
            "runtime_capabilities_required": capabilities,
            "output_contracts": [_output_contract(item, execution_policy, core_managed=item in core_managed_outputs) for item in expected_outputs],
        }
    )
    if human_required:
        # Human choices are persisted by the Studio decision surface, never task-submit/task-complete.
        enriched["submission_command"] = ""
        enriched["completion_command"] = ""
        enriched["forbidden_shortcuts"] = [
            item
            for item in enriched.get("forbidden_shortcuts") or []
            if "task-submit and task-complete" not in str(item)
        ]
        enriched["forbidden_shortcuts"].extend(
            [
                "Do not treat the Agent or a delegated runtime as the decision maker for this boundary.",
                "Do not create an agent completion marker or a substitute approval file; use the Studio decision interface.",
            ]
        )
    return enriched


def _output_contract(path: str, execution_policy: str, *, core_managed: bool = False) -> dict[str, str]:
    normalized = _normalize_rel(path)
    lower = normalized.lower()
    if core_managed:
        kind = "deterministic"
        policy = "automatic"
    elif lower.endswith("agent_completion.json") or ".agent_completion." in lower:
        kind = "completion-evidence"
        policy = "automatic"
    elif "approval" in lower or lower.startswith("decisions/"):
        kind = "human-approval"
        policy = "approval-required"
    elif execution_policy == "deterministic":
        kind = "deterministic"
        policy = "automatic"
    else:
        kind = "agent-authored"
        policy = "approval-required" if lower.startswith(HIGH_IMPACT_OUTPUT_PREFIXES) else "preview-required"
    return {"path": normalized, "kind": kind, "writeback_policy": policy}


def _workflow_payload(root: Path, route: str, scene: Path | str | None = None) -> dict[str, object]:
    if route == "scene-development":
        state = next_scene_workflow_state(root, scene)
        return {"scenes": [state] if state else []}
    result = build_workflow_state(root, route=route)
    return _read_json(result.json_path)


def _select_scene_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    scenes = [item for item in payload.get("scenes", []) if isinstance(item, dict)]
    if scene:
        scene_path = _resolve_project_path(root, scene)
        scene_id = _scene_id(scene_path)
        scene_rel = _rel(scene_path, root)
        return next((item for item in scenes if item.get("scene_id") == scene_id or item.get("scene") == scene_rel), None)
    return next((item for item in scenes if item.get("status") != "ready"), None)


def _select_longform_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    _ = scene
    state = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if not state or state.get("status") == "ready":
        return None
    return state


def _select_source_ingest_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("source_ingests", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("work_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("import_dir") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_style_engineering_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("styles", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("profile_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("profile_dir") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_asset_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("assets", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("candidate_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("candidate") or "").rstrip("/").endswith(target)
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_review_audit_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    _ = scene
    items = [item for item in payload.get("audits", []) if isinstance(item, dict)]
    return next((item for item in items if item.get("status") != "ready"), None)


def _select_export_release_state(root: Path, payload: dict[str, object], scene: Path | str | None) -> dict[str, object] | None:
    _ = root
    items = [item for item in payload.get("exports", []) if isinstance(item, dict)]
    if scene:
        target = str(scene).replace("\\", "/").strip("/")
        return next(
            (
                item
                for item in items
                if str(item.get("chapter_id") or "") == target
                or str(item.get("target_id") or "") == target
                or str(item.get("scene_id") or "") == target
            ),
            None,
        )
    return next((item for item in items if item.get("status") != "ready"), None)


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


def _state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    """Run current-state-specific gates after expected outputs exist."""

    current_state = str(task.get("current_state") or "")
    scene_id = str(task.get("scene_id") or "")
    errors: list[str] = []
    notes: list[str] = []
    if not current_state:
        return errors, notes

    if current_state in {"context-packet", "context-trace"}:
        errors.extend(_context_trace_gate_errors(root, scene_id))
    if current_state == "roleplay-simulation":
        errors.extend(_roleplay_gate_errors(root, scene_id))
    if current_state in {"branch-manifest", "branch-agent-task"}:
        errors.extend(_branch_manifest_gate_errors(root, scene_id))
    if current_state == "branch-selection":
        branch_errors, branch_notes = _branch_selection_gate(root, scene_id)
        errors.extend(branch_errors)
        notes.extend(branch_notes)
    if current_state in {"composition-json", "composition-agent-task"}:
        errors.extend(_composition_gate_errors(root, scene_id))
    if current_state == "scene-word-budget-contract":
        errors.extend(_word_budget_gate_errors(root, task))
    if current_state == "reader-experience-contract":
        errors.extend(_reader_experience_gate_errors(root, task))
    if current_state == "scene-rhythm-contract":
        errors.extend(_narrative_rhythm_gate_errors(root, scene_id))
    if current_state in {"candidate-generation-provenance", "generation-agent-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
    if current_state == "candidate-revision":
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
        errors.extend(_scene_revision_gate_errors(root, task, candidate))
    if current_state in {"candidate-review", "agent-review-task"}:
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_review_gate_errors(root, task, candidate, require_pass=current_state == "agent-review-task"))
    if current_state in {"promotion-manifest", "promoted-draft"}:
        errors.extend(_promotion_gate_errors(root, task))
    if current_state == "static-review":
        errors.extend(_static_review_gate_errors(root, scene_id, require_pass=False))
    if current_state == "static-revision":
        candidate = _candidate_path_for_task(root, task)
        errors.extend(_candidate_generation_gate_errors(root, task, candidate))
        errors.extend(_candidate_body_gate_errors(root, task, candidate))
        errors.extend(_scene_revision_gate_errors(root, task, candidate))
    if current_state in {"state-patch-json", "state-agent-task"}:
        errors.extend(_state_patch_gate_errors(root, scene_id))
    if current_state in {"canon-patch-json", "canon-agent-task"}:
        errors.extend(_canon_writeback_gate_errors(root, scene_id))
    return errors, notes


def _longform_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "word-budget-file":
        errors.extend(_word_budget_file_gate_errors(root))
    if current_state in {"budget-agent-task", "budget-review"}:
        errors.extend(_word_budget_file_gate_errors(root))
        errors.extend(_longform_sidecar_completion_errors(root / "plot" / "word_budget" / "word_budget.agent_tasks.md", root, "word-budget expansion"))
        errors.extend(
            _longform_required_artifact_errors(
                root,
                [root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"],
                "word-budget expansion",
            )
        )
        errors.extend(_longform_review_gate_errors(root / "reviews" / "word_budget" / "word_budget_review.md", root, "word-budget review", require_pass=current_state == "budget-review"))
        if current_state == "budget-review":
            errors.extend(_declared_repair_targets_changed(root, task, "word-budget revision"))
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"}:
        errors.extend(_word_budget_file_gate_errors(root))
        errors.extend(_longform_sidecar_completion_errors(root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md", root, "scene-inventory expansion"))
        errors.extend(
            _longform_required_artifact_errors(
                root,
                [root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"],
                "scene-inventory expansion",
            )
        )
        errors.extend(_longform_review_gate_errors(root / "reviews" / "word_budget" / "scene_inventory_review.md", root, "scene-inventory review", require_pass=current_state == "scene-inventory-review"))
        if current_state == "scene-inventory-review":
            errors.extend(_declared_repair_targets_changed(root, task, "scene-inventory revision"))
    if current_state in {"chapter-obligation-agent-task", "chapter-obligation-review"}:
        errors.extend(_word_budget_file_gate_errors(root))
        errors.extend(_longform_sidecar_completion_errors(root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md", root, "chapter obligation planning"))
        errors.extend(
            _longform_required_artifact_errors(
                root,
                [root / "plot" / "candidates" / "chapters" / "chapter_obligation_plan.md"],
                "chapter obligation planning",
            )
        )
        errors.extend(_longform_review_gate_errors(root / "reviews" / "word_budget" / "chapter_obligation_review.md", root, "chapter obligation review", require_pass=current_state == "chapter-obligation-review"))
        if current_state == "chapter-obligation-review":
            errors.extend(_declared_repair_targets_changed(root, task, "chapter-obligation revision"))
    if current_state in {"budget-agent-task", "budget-review"} and not errors:
        notes.append("word-budget expansion reviewed")
    if current_state in {"scene-inventory-agent-task", "scene-inventory-review"} and not errors:
        notes.append("scene inventory reviewed")
    if current_state in {"chapter-obligation-agent-task", "chapter-obligation-review"} and not errors:
        notes.append("chapter obligation reviewed")
    if current_state == "planning-materialization":
        passed, message = longform_materialization_status(root)
        if not passed:
            errors.append(message)
        else:
            notes.append(message)
    return errors, notes


def _source_ingest_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    import_dir = _source_import_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "source-manifest":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
    if current_state == "extraction-agent-task":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
        errors.extend(_source_extraction_gate_errors(root, import_dir, work_id, require_review_pass=False))
    if current_state == "extraction-review":
        errors.extend(_source_manifest_gate_errors(root, import_dir))
        errors.extend(_source_extraction_gate_errors(root, import_dir, work_id, require_review_pass=True))
        errors.extend(_source_extraction_revision_gate_errors(root, task))
    if current_state == "extraction-agent-task" and not errors:
        notes.append("source extraction candidates and sidecar completion marker exist")
    if current_state == "extraction-review" and not errors:
        notes.append("source extraction review passed")
    return errors, notes


def _style_engineering_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    profile_dir = _style_profile_dir_for_task(root, task)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "style-profile":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
    if current_state == "style-prompt-task-file":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        if not (profile_dir / "style_prompt.agent_tasks.md").exists():
            errors.append(f"style prompt task sidecar missing: {_rel(profile_dir / 'style_prompt.agent_tasks.md', root)}")
    if current_state == "style-prompt-agent-task":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir, require_quality=False))
    if current_state == "style-prompt-quality":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir, require_quality=True))
    if current_state == "style-eval-setup":
        errors.extend(_style_eval_reference_gate_errors(root, profile_dir))
    if current_state == "style-eval-task-file":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(_style_eval_reference_gate_errors(root, profile_dir))
        if not (profile_dir / "evaluation_results" / "formal" / "platform_agent_candidate.agent_tasks.md").is_file():
            errors.append("formal style evaluation sidecar is missing")
    if current_state == "style-eval-agent-task":
        errors.extend(_style_profile_gate_errors(root, profile_dir))
        errors.extend(_style_prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(_style_eval_agent_gate_errors(root, profile_dir))
    if current_state == "style-eval-score-file":
        errors.extend(_style_eval_agent_gate_errors(root, profile_dir))
        errors.extend(_style_eval_current_score_errors(root, profile_dir, require_accepted=False))
    if current_state == "style-eval-revision":
        errors.extend(_declared_repair_targets_changed(root, task, "style-evaluation revision"))
        errors.extend(_style_prompt_gate_errors(root, profile_dir, require_quality=True))
        errors.extend(_style_eval_agent_gate_errors(root, profile_dir))
        if not _style_eval_score_is_stale(profile_dir):
            errors.append("style evaluation revision must make the previous deterministic score stale")
    if current_state == "style-eval-readiness":
        errors.extend(_style_eval_current_score_errors(root, profile_dir, require_accepted=True))
    if current_state in {"style-prompt-agent-task", "style-prompt-quality"} and not errors:
        notes.append("style prompt task completed and quality gate passed")
    if current_state == "style-eval-agent-task" and not errors:
        notes.append("style evaluation candidate completed; deterministic scoring is next")
    if current_state == "style-eval-score-file" and not errors:
        notes.append("deterministic style score recorded for the exact current candidate")
    if current_state == "style-eval-revision" and not errors:
        notes.append("style prompt/evaluation candidate revised; fresh deterministic scoring is required")
    if current_state == "style-eval-readiness" and not errors:
        notes.append("style evaluation readiness passed")
    return errors, notes


def _asset_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    candidate = _asset_candidate_path_for_task(root, task)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or candidate.stem)
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "asset-intake":
        errors.extend(_asset_intake_gate_errors(root))
    if current_state == "asset-creation-agent-task":
        errors.extend(_asset_creation_gate_errors(root, candidate))
    if current_state == "asset-review-task-file":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        review_task = root / "reviews" / "assets" / f"{candidate_id}_review.agent_tasks.md"
        if not review_task.exists():
            errors.append(f"asset review sidecar missing: {_rel(review_task, root)}")
    if current_state == "asset-review-agent-task":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=False))
    if current_state in {"asset-review-pass", "asset-approval-revision"}:
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_revision_gate_errors(root, task, candidate, candidate_id))
    if current_state == "asset-approval":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id, candidate))
    if current_state == "asset-promotion":
        errors.extend(_asset_creation_gate_errors(root, candidate))
        errors.extend(_asset_review_gate_errors(root, candidate_id, require_pass=True))
        errors.extend(_asset_approval_gate_errors(root, candidate_id, candidate))
        errors.extend(_asset_promotion_gate_errors(root, candidate_id))
    if current_state in {"asset-creation-agent-task", "asset-review-task-file"} and not errors:
        notes.append("asset candidate creation gate passed")
    if current_state == "asset-review-agent-task" and not errors:
        notes.append("asset review verdict recorded; pass or formal revision routing may continue")
    if current_state in {"asset-review-pass", "asset-approval-revision"} and not errors:
        notes.append("asset candidate revised and prior review evidence reset for independent recheck")
    if current_state == "asset-promotion" and not errors:
        notes.append("asset promotion gate passed")
    return errors, notes


def _review_audit_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "canon-patch-revision":
        errors.extend(_declared_repair_targets_changed(root, task, "canon-patch revision"))
        errors.extend(_canon_patch_candidate_gate_errors(root, task))
    if current_state == "canon-patch-approval":
        errors.extend(_canon_patch_candidate_gate_errors(root, task))
        errors.extend(_canon_patch_decision_gate_errors(root, task, require_approve=False))
    if current_state == "canon-patch-deferred":
        errors.append("canon patch is intentionally deferred; resume it through an explicit new decision")
    if current_state == "canon-patch-apply":
        errors.extend(_canon_patch_apply_gate_errors(root, task))
    if current_state == "canon-lint-file":
        errors.extend(_canon_lint_gate_errors(root))
    if current_state == "canon-review-task-file":
        errors.extend(_canon_lint_gate_errors(root))
        canon_task = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
        if not canon_task.exists():
            errors.append(f"canon review sidecar missing: {_rel(canon_task, root)}")
    if current_state == "canon-review-agent-task":
        errors.extend(_canon_lint_gate_errors(root))
        errors.extend(_canon_review_gate_errors(root, require_pass=False))
    if current_state == "canon-review-pass":
        errors.extend(_project_review_revision_gate_errors(root, task, review_kind="canon"))
    if current_state == "longform-audit-file":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
    if current_state == "committee-task-file":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
        committee_task = root / "reviews" / "agent" / "committee_project-final-audit.agent_tasks.md"
        if not committee_task.exists():
            errors.append(f"committee sidecar missing: {_rel(committee_task, root)}")
    if current_state == "committee-agent-task":
        errors.extend(_canon_review_gate_errors(root, require_pass=True))
        errors.extend(_longform_audit_file_gate_errors(root))
        errors.extend(_committee_review_gate_errors(root, require_approve=False))
    if current_state == "committee-pass":
        errors.extend(_project_review_revision_gate_errors(root, task, review_kind="committee"))
    if current_state == "canon-patch-revision" and not errors:
        notes.append("canon patch candidate revised; fresh content-bound approval is required")
    if current_state == "canon-patch-approval" and not errors:
        notes.append("canon patch decision recorded against the current candidate")
    if current_state == "canon-patch-apply" and not errors:
        notes.append("approved canon patch applied to durable ledger")
    if current_state == "canon-review-agent-task" and not errors:
        notes.append("canon review verdict recorded; clean pass or formal revision routing may continue")
    if current_state == "canon-review-pass" and not errors:
        notes.append("canon repair completed; deterministic lint refreshed and review evidence reset")
    if current_state == "committee-agent-task" and not errors:
        notes.append("committee verdict recorded; approval or formal revision routing may continue")
    if current_state == "committee-pass" and not errors:
        notes.append("committee repair completed; project audits refreshed and review evidence reset")
    return errors, notes


def _export_release_state_gate_validation(root: Path, task: dict[str, object]) -> tuple[list[str], list[str]]:
    current_state = str(task.get("current_state") or "")
    chapter_id = str(task.get("chapter_id") or task.get("target_id") or task.get("scene_id") or "chapter_0001")
    errors: list[str] = []
    notes: list[str] = []
    if current_state == "chapter-workspace":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
    if current_state == "export-package":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
    if current_state == "release-approval":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
        errors.extend(_release_approval_gate_errors(root, chapter_id))
    if current_state == "publish-release":
        errors.extend(_chapter_workspace_gate_errors(root, chapter_id))
        errors.extend(_export_package_gate_errors(root, chapter_id))
        errors.extend(_release_approval_gate_errors(root, chapter_id))
        errors.extend(_publish_release_gate_errors(root, chapter_id))
    if current_state == "export-package" and not errors:
        notes.append("export package ready with no skipped scenes")
    if current_state == "publish-release" and not errors:
        notes.append("chapter published through approved release gate")
    return errors, notes


def _canon_patch_path_for_task(root: Path, task: dict[str, object]) -> Path:
    patch = str(task.get("patch") or "").strip()
    if patch:
        return _resolve_project_path(root, patch)
    for value in [*task.get("expected_outputs", []), *task.get("source_paths", [])]:
        relative = str(value).replace("\\", "/")
        if relative.startswith("canon/patches/") and relative.endswith("_canon_patch.json"):
            return _resolve_project_path(root, relative)
    return root / "canon" / "patches" / "missing_canon_patch.json"


def _canon_patch_candidate_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    payload, error = _read_optional_json(patch)
    if error:
        return [error]
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-candidate/v0.1":
        errors.append("canon patch has wrong or missing schema")
    if payload.get("canon_change") is not True:
        errors.append("canon patch must declare canon_change=true before project-level approval")
    if payload.get("applied") is True or str(payload.get("status") or "").strip().lower() == "applied":
        errors.append("canon patch revision/approval task must not mark the candidate applied")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        errors.append("canon patch must contain at least one durable fact item")
    required = ("type", "summary", "source_evidence", "target_files", "risk_level", "requires_user_approval")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"canon patch item {index + 1} must be an object")
            continue
        missing = [
            field
            for field in required
            if field not in item or item.get(field) is None or item.get(field) == "" or item.get(field) == []
        ]
        if missing:
            errors.append(f"canon patch item {index + 1} missing fields: {', '.join(missing)}")
        targets = item.get("target_files") if isinstance(item.get("target_files"), list) else []
        for target in targets:
            value = str(target).replace("\\", "/")
            if Path(value).is_absolute() or ".." in Path(value).parts or not value.startswith("canon/"):
                errors.append(f"canon patch item {index + 1} has unsafe target_file: {value}")
    completion = agent_task_completion_status(patch.with_suffix(".agent_tasks.md"), root=root)
    if completion.get("complete") is not True:
        errors.append(f"canon-evolve sidecar is incomplete: {completion.get('message')}")
    report = patch.with_suffix(".md")
    if not report.is_file():
        errors.append(f"canon patch report missing: {_rel(report, root)}")
    return errors


def _canon_patch_decision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    require_approve: bool,
) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    approval = _approval_record_for_run(root, patch_id)
    decision = str(approval.get("decision") or "").strip().lower()
    allowed = {"approve"} if require_approve else {"approve", "revise", "reject", "defer"}
    if decision not in allowed:
        return [f"canon patch decision for {patch_id} must be one of {sorted(allowed)}; got {decision or 'missing'}"]
    if not _approval_matches_file(approval, patch):
        return [f"canon patch decision for {patch_id} is stale or not bound to the current candidate"]
    return []


def _canon_patch_apply_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    patch = _canon_patch_path_for_task(root, task)
    patch_id = str(task.get("patch_id") or patch.stem)
    apply_manifest = root / "canon" / "applied" / f"{patch_id}_apply.json"
    payload, error = _read_optional_json(apply_manifest)
    if error:
        return [error]
    errors: list[str] = []
    if payload.get("schema") != "literary-engineering-workbench/canon-patch-apply/v0.1":
        errors.append("canon apply manifest has wrong or missing schema")
    if payload.get("status") != "applied":
        errors.append(f"canon apply status must be applied; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved") is True:
        errors.append("canon apply used allow_unapproved")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    candidate_sha256 = str(payload.get("candidate_sha256") or "").strip().lower()
    if approval.get("decision") != "approve":
        errors.append("canon apply manifest must carry an approve record")
    if not candidate_sha256 or str(approval.get("subject_sha256") or "").strip().lower() != candidate_sha256:
        errors.append("canon apply approval digest does not match the pre-apply patch candidate")
    patch_payload, patch_error = _read_optional_json(patch)
    if patch_error:
        errors.append(patch_error)
    elif patch_payload.get("applied") is not True or patch_payload.get("apply_manifest") != _rel(apply_manifest, root):
        errors.append("canon patch does not point to its applied manifest")
    if not (root / "canon" / "canon_change_log.md").is_file():
        errors.append("canon change log is missing after apply")
    return errors


def _canon_lint_gate_errors(root: Path) -> list[str]:
    json_path = root / "reviews" / "canon_lint.json"
    report_path = root / "reviews" / "canon_lint.md"
    errors: list[str] = []
    for path in (report_path, json_path):
        if not path.exists():
            errors.append(f"canon-lint artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/canon-lint/v0.1":
        errors.append("canon_lint.json has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocking = _to_int(summary.get("blocking_count"))
    status = str(payload.get("status") or "").strip().lower()
    if blocking:
        errors.append(f"canon-lint blocking_count must be 0; got {blocking}")
    if status not in {"pass", "pass_with_warnings"}:
        errors.append(f"canon-lint status must be pass/pass_with_warnings; got {status or 'missing'}")
    return errors


def _canon_review_gate_errors(root: Path, *, require_pass: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "canon_review.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"canon review sidecar is incomplete: {state.get('message')}")
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"canon review artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "canon_review.v1")
    errors.extend(f"canon_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    if require_pass:
        conclusion = str(payload.get("conclusion") or "").strip().lower()
        blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
        warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
        unresolved = payload.get("unresolved_facts") if isinstance(payload.get("unresolved_facts"), list) else []
        timeline = payload.get("timeline_risks") if isinstance(payload.get("timeline_risks"), list) else []
        if conclusion != "pass":
            errors.append(f"canon review conclusion must be pass; got {conclusion or 'missing'}")
        if blocking:
            errors.append(f"canon review blocking_issues must be empty; got {len(blocking)}")
        if warnings:
            errors.append(f"canon review warnings must be resolved before export/release; got {len(warnings)}")
        if unresolved:
            errors.append(f"canon review unresolved_facts must be empty; got {len(unresolved)}")
        if timeline:
            errors.append(f"canon review timeline_risks must be empty; got {len(timeline)}")
    return errors


def _project_review_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    *,
    review_kind: str,
) -> list[str]:
    errors: list[str] = []
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    if not targets:
        errors.append(f"{review_kind} revision has no declared repair_targets; reviewer must provide exact target_path values")
    changed = False
    for relative in targets:
        path = _resolve_project_path(root, relative)
        if not path.is_file():
            errors.append(f"declared review repair target missing after revision: {relative}")
            continue
        previous = str(hashes.get(relative) or "")
        if not previous or _file_sha256(path) != previous:
            changed = True
    if targets and not changed:
        errors.append("project review repair did not change any declared repair target")

    def reset_errors(prefix: str) -> None:
        json_path = root / "reviews" / "agent" / f"{prefix}.json"
        task_path = json_path.with_suffix(".agent_tasks.md")
        completion = default_agent_completion_path(task_path)
        payload, payload_error = _read_optional_json(json_path)
        if payload_error:
            errors.append(payload_error)
        else:
            field = "conclusion" if prefix == "canon_review" else "final_recommendation"
            status = str(payload.get(field) or "").strip().lower()
            if status != "recheck_required":
                errors.append(f"{prefix} {field} must be recheck_required after revision; got {status or 'missing'}")
            applied = payload.get("applied_repair_actions")
            if not isinstance(applied, list) or not applied:
                errors.append(f"{prefix} must record non-empty applied_repair_actions")
        marker, marker_error = _read_optional_json(completion)
        if marker_error:
            errors.append(marker_error)
        else:
            marker_status = str(marker.get("status") or "").strip().lower()
            if marker_status != "recheck_required":
                errors.append(f"{prefix} completion status must be recheck_required after revision")
            if marker.get("expected_artifacts_checked") is not False:
                errors.append(f"{prefix} completion expected_artifacts_checked must be false after revision")

    reset_errors("canon_review")
    errors.extend(_canon_lint_gate_errors(root))
    if review_kind == "committee":
        reset_errors("committee_project-final-audit")
        errors.extend(_longform_audit_file_gate_errors(root))
    return errors


def _longform_audit_file_gate_errors(root: Path) -> list[str]:
    json_path = root / "reviews" / "longform" / "longform_audit.json"
    report_path = json_path.with_suffix(".md")
    graph_path = root / "plot" / "longform_graph.json"
    errors: list[str] = []
    for path in (json_path, report_path, graph_path):
        if not path.exists():
            errors.append(f"longform audit artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/longform-audit/v0.1":
        errors.append("longform_audit.json has wrong or missing schema")
    if not isinstance(payload.get("summary"), dict):
        errors.append("longform_audit.json must contain summary")
    return errors


def _committee_review_gate_errors(root: Path, *, require_approve: bool) -> list[str]:
    json_path = root / "reviews" / "agent" / "committee_project-final-audit.json"
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"committee review sidecar is incomplete: {state.get('message')}")
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"committee review artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    schema_errors, _warnings = validate_payload(payload, "committee_review.v1")
    errors.extend(f"committee_review.v1 schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
    if require_approve:
        recommendation = str(payload.get("final_recommendation") or "").strip().lower()
        action_items = payload.get("action_items") if isinstance(payload.get("action_items"), list) else []
        disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
        if recommendation != "approve":
            errors.append(f"committee final_recommendation must be approve; got {recommendation or 'missing'}")
        if action_items:
            errors.append(f"committee action_items must be empty before export/release; got {len(action_items)}")
        if disagreements:
            errors.append(f"committee disagreements must be empty before export/release; got {len(disagreements)}")
    return errors


def _chapter_workspace_gate_errors(root: Path, chapter_id: str) -> list[str]:
    json_path = root / "plot" / "chapters" / f"{chapter_id}.json"
    report_path = root / "drafts" / "chapters" / f"{chapter_id}.md"
    errors: list[str] = []
    for path in (json_path, report_path):
        if not path.exists():
            errors.append(f"chapter workspace artifact missing: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/chapter-workspace/v0.1":
        errors.append("chapter workspace JSON has wrong or missing schema")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if _to_int(summary.get("ready_count")) <= 0:
        errors.append("chapter workspace ready_count must be positive")
    if _to_int(summary.get("blocked_count")) != 0:
        errors.append(f"chapter workspace blocked_count must be 0; got {summary.get('blocked_count')}")
    for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or "")
        if scene.get("status") != "ready":
            errors.append(f"chapter scene must be ready: {scene_id or 'unknown'}")
        if scene.get("agent_review_conclusion") != "pass" or scene.get("agent_review_schema_status") != "pass":
            errors.append(f"chapter scene lacks clean platform AgentReview: {scene_id or 'unknown'}")
        if scene.get("agent_review_source_match") is not True:
            errors.append(f"chapter scene AgentReview does not cite exact draft/candidate: {scene_id or 'unknown'}")
        if scene.get("agent_review_unresolved_notes"):
            errors.append(f"chapter scene has unresolved AgentReview notes: {scene_id or 'unknown'}")
        if scene.get("flow_gate_issues") or scene.get("readiness_issues"):
            errors.append(f"chapter scene has unresolved flow/readiness gate issues: {scene_id or 'unknown'}")
    return errors


def _export_package_gate_errors(root: Path, chapter_id: str) -> list[str]:
    manifest_path = root / "exports" / chapter_id / "export_manifest.json"
    errors: list[str] = []
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/export-package/v0.1":
        errors.append("export_manifest.json has wrong or missing schema")
    if payload.get("include_blocked") is True:
        errors.append("export package must not use include_blocked for formal delivery")
    requested_formats = {str(item).strip().lower() for item in payload.get("requested_formats", []) if str(item).strip()}
    if not {"md", "docx"}.issubset(requested_formats):
        errors.append("formal export package must include requested_formats md and docx")
    skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
    if skipped:
        errors.append(f"export package skipped_scenes must be empty; got {len(skipped)}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    for key in ("novel", "screenplay", "video_prompt_pack"):
        rel = str(outputs.get(key) or "")
        if not rel:
            errors.append(f"export output missing from manifest: {key}")
            continue
        path = root / rel
        if not path.exists():
            errors.append(f"export output file missing: {rel}")
            continue
        hits = _delivery_trace_hits(path)
        if hits:
            errors.append(f"export output contains workbench traces in {rel}: {', '.join(hits[:5])}")
    docx_outputs = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
    layouts = outputs.get("docx_layout_plans") if isinstance(outputs.get("docx_layout_plans"), dict) else {}
    inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
    for key in ("novel", "screenplay", "video_prompt_pack"):
        for label, values in (("DOCX", docx_outputs), ("DOCX layout", layouts), ("DOCX inspection", inspections)):
            rel = str(values.get(key) or "")
            if not rel or not (root / rel).is_file():
                errors.append(f"{label} output missing: {key} -> {rel or 'missing'}")
    return errors


def _release_approval_gate_errors(root: Path, chapter_id: str) -> list[str]:
    run_id = f"release-{chapter_id}"
    approval = _approval_record_for_run(root, run_id)
    fingerprint = release_candidate_fingerprint(root, chapter_id)
    if str(approval.get("decision") or "") == "approve" and fingerprint and str(approval.get("subject_sha256") or "").lower() == fingerprint:
        return []
    return [f"release approval missing, stale, or not approve for current export manifest and run_id {run_id}"]


def _publish_release_gate_errors(root: Path, chapter_id: str) -> list[str]:
    release_dir = root / "releases" / chapter_id / "formal-release"
    manifest = release_dir / "publish_manifest.json"
    latest = root / "releases" / chapter_id / "latest.json"
    errors: list[str] = []
    payload, error = _read_optional_json(manifest)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/publish-chapter/v0.1":
        errors.append("publish_manifest.json has wrong or missing schema")
    if payload.get("status") != "published":
        errors.append(f"publish status must be published; got {payload.get('status') or 'missing'}")
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    if approval.get("decision") != "approve":
        errors.append("publish manifest approval must be an approve record")
    approved_fingerprint = str(payload.get("approved_export_fingerprint") or "").strip().lower()
    if not approved_fingerprint or str(approval.get("subject_sha256") or "").strip().lower() != approved_fingerprint:
        errors.append("publish manifest approval does not match the approved export fingerprint")
    outputs = payload.get("published_outputs") if isinstance(payload.get("published_outputs"), dict) else {}
    if not outputs:
        errors.append("publish manifest must contain published_outputs")
    for key, rel in outputs.items():
        if not (root / str(rel)).exists():
            errors.append(f"published output missing: {key} -> {rel}")
    latest_payload, latest_error = _read_optional_json(latest)
    if latest_error:
        errors.append(latest_error)
    elif latest_payload.get("manifest") != _rel(manifest, root):
        errors.append("latest.json does not point to formal-release publish_manifest.json")
    return errors


def _delivery_trace_hits(path: Path) -> list[str]:
    text = _read_text(path)
    patterns = {
        "scene-id": r"\bscene_\d{4}\b",
        "agent-task": r"\[AGENT_TASK:",
        "canon-note-heading": r"(?m)^#{1,4}\s*(新增事实候选|人物状态变化|关系变化|伏笔变化|需要人工确认|世界状态变化|状态变化候选)\s*$",
        "review-heading": r"(?m)^#{1,4}\s*(审查|AgentReview|Route Audit|平台 Agent 任务|门禁问题汇总)\b",
        "workflow-path": r"\b(workflow/tasks|reviews/agent|characters/state_patches|drafts/promotions|branch_manifest|roleplay_simulation)\b",
    }
    hits = []
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            hits.append(label)
    return hits


def _word_budget_file_gate_errors(root: Path) -> list[str]:
    json_path = root / "plot" / "word_budget" / "word_budget.json"
    markdown_path = root / "plot" / "word_budget" / "word_budget.md"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    errors: list[str] = []
    for path in (markdown_path, json_path, budget_task, scene_task, obligation_task):
        if not path.exists():
            errors.append(f"missing longform budget artifact: {_rel(path, root)}")
    payload, error = _read_optional_json(json_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/word-budget/v1":
        errors.append("word_budget.json has wrong or missing schema")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if _to_int(target.get("target_words") or totals.get("target_words")) <= 0:
        errors.append("word_budget.json target Chinese-content characters must be positive")
    if not isinstance(payload.get("chapter_budgets"), list) or not payload.get("chapter_budgets"):
        errors.append("word_budget.json must contain chapter_budgets")
    if not isinstance(payload.get("scene_inventory_binding"), dict):
        errors.append("word_budget.json must contain scene_inventory_binding")
    return errors


def _longform_sidecar_completion_errors(task_path: Path, root: Path, label: str) -> list[str]:
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is True:
        return []
    return [f"{label} sidecar is incomplete: {state.get('message')}"]


def _longform_required_artifact_errors(root: Path, paths: list[Path], label: str) -> list[str]:
    missing = [_rel(path, root) for path in paths if not path.exists()]
    if not missing:
        return []
    return [f"{label} required artifact missing: {', '.join(missing)}"]


def _longform_review_gate_errors(path: Path, root: Path, label: str, *, require_pass: bool = True) -> list[str]:
    conclusion = _static_review_conclusion(path)
    allowed = {"pass", "pass_with_notes", "revise_required", "reject"}
    if conclusion not in allowed:
        return [f"{label} conclusion must be recorded; got {conclusion or 'missing'} at {_rel(path, root)}"]
    if not require_pass or conclusion == "pass":
        return []
    return [f"{label} conclusion must be pass; got {conclusion or 'missing'} at {_rel(path, root)}"]


def _declared_repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    if not targets or not hashes:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = _resolve_project_path(root, target)
        previous = str(hashes.get(target) or "").strip().lower()
        if path.is_file() and previous and _file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def _source_manifest_gate_errors(root: Path, import_dir: Path) -> list[str]:
    manifest_path = import_dir / "source_manifest.json"
    report_path = import_dir / "source_ingest.md"
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    errors: list[str] = []
    for path in (manifest_path, report_path, task_path):
        if not path.exists():
            errors.append(f"missing source-ingest artifact: {_rel(path, root)}")
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
        return errors
    if payload.get("schema") != "literary-engineering-workbench/source-ingest/v1":
        errors.append("source_manifest.json has wrong or missing schema")
    if not payload.get("work_id"):
        errors.append("source_manifest.json must contain work_id")
    if not isinstance(payload.get("chunks"), list) or not payload.get("chunks"):
        errors.append("source_manifest.json must contain source chunks")
    if not isinstance(payload.get("candidate_outputs"), dict) or not payload.get("candidate_outputs"):
        errors.append("source_manifest.json must contain candidate_outputs")
    return errors


def _source_extraction_gate_errors(root: Path, import_dir: Path, work_id: str, *, require_review_pass: bool) -> list[str]:
    manifest = _read_json(import_dir / "source_manifest.json")
    outputs = _source_candidate_outputs_from_manifest(manifest, work_id or import_dir.name)
    task_path = import_dir / "extract_project_files.agent_tasks.md"
    state = agent_task_completion_status(task_path, root=root)
    errors: list[str] = []
    if state.get("complete") is not True:
        errors.append(f"source extraction sidecar is incomplete: {state.get('message')}")
    for key, rel in outputs.items():
        path = root / rel
        if not path.exists():
            errors.append(f"source extraction output missing: {key} -> {rel}")
    if require_review_pass:
        review = root / outputs.get("review", f"reviews/source_ingest/{work_id}_extraction_review.md")
        conclusion = _static_review_conclusion(review)
        if conclusion != "pass":
            errors.append(f"source-ingest extraction review conclusion must be pass; got {conclusion or 'missing'} at {_rel(review, root)}")
    return errors


def _source_extraction_revision_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    before = task.get("repair_target_sha256_before_revision")
    if not isinstance(before, dict) or not before:
        return ["source extraction revision task is missing repair target hash provenance"]
    changed = False
    for relative, digest in before.items():
        path = _resolve_project_path(root, str(relative))
        if path.is_file() and _file_sha256(path) != str(digest).strip().lower():
            changed = True
            break
    return [] if changed else ["source extraction candidates did not change; rewriting only the review cannot complete revision"]


def _source_import_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    work_id = str(task.get("work_id") or task.get("target_id") or task.get("scene_id") or "")
    source_paths = [str(item) for item in task.get("source_paths") or []]
    for item in source_paths:
        normalized = item.replace("\\", "/")
        if "/source_manifest.json" in f"/{normalized}":
            return _resolve_project_path(root, normalized).parent
    return root / "sources" / "imports" / (work_id or "source")


def _source_candidate_outputs_from_manifest(manifest: dict[str, object], work_id: str) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs") if isinstance(manifest.get("candidate_outputs"), dict) else {}
    if outputs:
        return {str(key): str(value) for key, value in outputs.items() if str(value).strip()}
    return {
        "project_brief": f"sources/imports/{work_id}/extracted/project_brief.md",
        "characters": f"characters/candidates/extracted/{work_id}_characters.md",
        "world": f"canon/candidates/extracted/{work_id}_world.md",
        "outline": f"plot/candidates/extracted/{work_id}_outline.md",
        "timeline": f"plot/candidates/extracted/{work_id}_timeline.md",
        "foreshadowing": f"plot/candidates/extracted/{work_id}_foreshadowing.md",
        "style_notes": f"style/candidates/{work_id}_style_generation_notes.md",
        "review": f"reviews/source_ingest/{work_id}_extraction_review.md",
    }


def _style_profile_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in (profile_dir / "style-profile.md", profile_dir / "style_metrics.json"):
        if not path.exists():
            errors.append(f"style profile artifact missing: {_rel(path, root)}")
    return errors


def _style_prompt_gate_errors(root: Path, profile_dir: Path, *, require_quality: bool = True) -> list[str]:
    task_path = profile_dir / "style_prompt.agent_tasks.md"
    prompt_path = profile_dir / "style_prompt.md"
    agent_json = profile_dir / "style_prompt.agent.json"
    errors: list[str] = []
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"style prompt sidecar is incomplete: {state.get('message')}")
    for path in (prompt_path, agent_json):
        if not path.exists():
            errors.append(f"style prompt artifact missing: {_rel(path, root)}")
    if prompt_path.exists() and require_quality:
        report = style_prompt_quality_report(_read_text(prompt_path))
        if not report.get("length_ok"):
            errors.append(
                "style_prompt.md detail length must be 500-2500 Chinese-content characters; "
                f"got {report.get('detail_chars')} ({report.get('detail_count_unit')})"
            )
        if not report.get("structure_ok"):
            missing = ", ".join(str(item) for item in report.get("missing_blocks", []))
            errors.append(f"style_prompt.md missing required prompt blocks: {missing}")
    return errors


def _style_eval_reference_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    references = [path for path in sorted((profile_dir / "corpus").glob("*.txt")) if path.is_file() and path.stat().st_size > 0]
    if references:
        return []
    return [f"authorized style evaluation reference missing under {_rel(profile_dir / 'corpus', root)}"]


def _style_eval_agent_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    eval_dir = profile_dir / "evaluation_results" / "formal"
    candidate = eval_dir / "platform_agent_candidate.md"
    manifest = eval_dir / "platform_agent_candidate.prompt.json"
    task = eval_dir / "platform_agent_candidate.agent_tasks.md"
    errors: list[str] = []
    completion = agent_task_completion_status(task, root=root)
    if completion.get("complete") is not True:
        errors.append(f"style evaluation sidecar is incomplete: {completion.get('message')}")
    if not candidate.is_file() or not _read_text(candidate).strip():
        errors.append(f"style evaluation candidate is missing or empty: {_rel(candidate, root)}")
    payload, error = _read_optional_json(manifest)
    if error:
        errors.append(error)
    else:
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in {"back-translation", "outline-expansion", "blind-review"}:
            errors.append(f"style evaluation prompt manifest has invalid mode: {mode or 'missing'}")
        for field in ("style_prompt", "reference", "input", "candidate"):
            if not str(payload.get(field) or "").strip():
                errors.append(f"style evaluation prompt manifest missing {field}")
    return errors


def _style_eval_score_is_stale(profile_dir: Path) -> bool:
    candidate = profile_dir / "evaluation_results" / "formal" / "platform_agent_candidate.md"
    current = profile_dir / "evaluation_results" / "formal" / "style_eval_current.json"
    if not candidate.is_file():
        return False
    payload, error = _read_optional_json(current)
    if error:
        return True
    return str(payload.get("candidate_sha256") or "").strip().lower() != _file_sha256(candidate)


def _style_eval_current_score_errors(root: Path, profile_dir: Path, *, require_accepted: bool) -> list[str]:
    eval_dir = profile_dir / "evaluation_results" / "formal"
    candidate = eval_dir / "platform_agent_candidate.md"
    current = eval_dir / "style_eval_current.json"
    report = eval_dir / "style_eval_current.md"
    payload, error = _read_optional_json(current)
    errors: list[str] = []
    if error:
        return [error]
    if not report.is_file():
        errors.append(f"current style evaluation report missing: {_rel(report, root)}")
    if payload.get("schema") != "literary-engineering-workbench/style-eval/v0.1":
        errors.append("current style evaluation JSON has wrong or missing schema")
    candidate_sha = _file_sha256(candidate) if candidate.is_file() else ""
    if not candidate_sha or str(payload.get("candidate_sha256") or "").strip().lower() != candidate_sha:
        errors.append("current style evaluation score is stale for the candidate digest")
    try:
        score = float(payload.get("overall_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    risk = str(payload.get("risk_level") or "").strip().lower()
    if require_accepted and (score < 45 or risk in {"high_copy_risk", "low_similarity"}):
        errors.append(f"style evaluation not accepted: overall_score={score}; risk_level={risk or 'missing'}")
    return errors


def _style_eval_gate_errors(root: Path, profile_dir: Path) -> list[str]:
    accepted = _accepted_style_eval_jsons(profile_dir)
    if accepted:
        return []
    return [f"accepted style_eval_*.json missing under {_rel(profile_dir / 'evaluation_results', root)}"]


def _accepted_style_eval_jsons(profile_dir: Path) -> list[Path]:
    accepted: list[Path] = []
    for path in sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json")):
        payload, error = _read_optional_json(path)
        if error:
            continue
        risk = str(payload.get("risk_level") or "")
        try:
            score = float(payload.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if risk in {"high_copy_risk", "low_similarity"} or score < 45:
            continue
        accepted.append(path)
    return accepted


def _style_profile_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    profile_dir = str(task.get("profile_dir") or "").strip()
    if profile_dir:
        return _resolve_project_path(root, profile_dir)
    source_paths = [str(item) for item in task.get("source_paths") or []]
    for item in source_paths:
        normalized = item.replace("\\", "/")
        if normalized.endswith("/style-profile.md"):
            return _resolve_project_path(root, normalized).parent
    profile_id = str(task.get("profile_id") or task.get("target_id") or task.get("scene_id") or "style-profile")
    return root / "style" / profile_id


def _asset_intake_gate_errors(root: Path) -> list[str]:
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if not base.exists():
            continue
        if any(base.glob("*.agent_tasks.md")) or any(base.glob("*.json")):
            return []
    return ["no candidate asset or asset creation sidecar exists; run seed-project-assets first"]


def _asset_creation_gate_errors(root: Path, candidate: Path) -> list[str]:
    errors: list[str] = []
    task_path = candidate.with_suffix(".agent_tasks.md")
    report_path = candidate.with_suffix(".md")
    state = agent_task_completion_status(task_path, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset creation sidecar is incomplete: {state.get('message')}")
    payload, error = _read_optional_json(candidate)
    if error:
        errors.append(error)
    else:
        asset_type = _asset_type_from_payload_or_path(root, candidate, payload)
        schema_name = ASSET_SCHEMA_NAMES.get(asset_type, "")
        if not schema_name:
            errors.append(f"unknown asset type for candidate: {asset_type or _rel(candidate, root)}")
        else:
            schema_errors, _warnings = validate_payload(payload, schema_name)
            errors.extend(f"asset candidate schema error at {item.get('path')}: {item.get('message')}" for item in schema_errors)
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            errors.append("asset candidate JSON must contain candidate_id")
        if not isinstance(payload.get("risks"), list):
            errors.append("asset candidate JSON must contain risks list")
        if not isinstance(payload.get("source_paths"), list):
            errors.append("asset candidate JSON must contain source_paths list")
        if not isinstance(payload.get("promotion_notes"), str) or not str(payload.get("promotion_notes") or "").strip():
            errors.append("asset candidate JSON must contain promotion_notes")
    if not report_path.exists():
        errors.append(f"asset candidate report missing: {_rel(report_path, root)}")
    return errors


def _asset_review_gate_errors(root: Path, candidate_id: str, *, require_pass: bool) -> list[str]:
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    errors: list[str] = []
    state = agent_task_completion_status(review_task, root=root)
    if state.get("complete") is not True:
        errors.append(f"asset review sidecar is incomplete: {state.get('message')}")
    payload, error = _read_optional_json(review_json)
    if error:
        errors.append(error)
    else:
        status = str(payload.get("status") or "").strip().lower()
        allowed_statuses = {"pass", "failed", "revise_required"}
        if status not in allowed_statuses:
            errors.append(
                f"asset review status must be one of {', '.join(sorted(allowed_statuses))}; "
                f"got {status or 'missing'} at {_rel(review_json, root)}"
            )
        if require_pass and status != "pass":
            errors.append(f"asset review status must be pass; got {status or 'missing'} at {_rel(review_json, root)}")
        blocking = payload.get("blocking_issues")
        if not isinstance(blocking, list):
            errors.append("asset review blocking_issues must be a list")
        elif require_pass and blocking:
            errors.append(f"asset review has blocking_issues: {len(blocking)}")
        revisions = payload.get("revision_actions")
        if not isinstance(revisions, list):
            errors.append("asset review revision_actions must be a list")
        elif require_pass and revisions:
            errors.append(f"asset review has unresolved revision_actions: {len(revisions)}")
        for field in ("warnings", "promotion_risks"):
            if not isinstance(payload.get(field), list):
                errors.append(f"asset review {field} must be a list")
        candidate_ref = str(payload.get("candidate") or "").strip()
        if candidate_ref and Path(candidate_ref).stem != candidate_id:
            errors.append(f"asset review candidate mismatch: {candidate_ref} does not match {candidate_id}")
    if not review.exists():
        errors.append(f"asset review report missing: {_rel(review, root)}")
    return errors


def _asset_revision_gate_errors(
    root: Path,
    task: dict[str, object],
    candidate: Path,
    candidate_id: str,
) -> list[str]:
    review = root / "reviews" / "assets" / f"{candidate_id}_review.md"
    review_json = review.with_suffix(".json")
    review_task = review_json.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(review_task)
    errors: list[str] = []

    previous_hash = str(task.get("candidate_sha256_before_revision") or "").strip().lower()
    if not previous_hash:
        errors.append("asset revision task is missing candidate_sha256_before_revision provenance")
    elif not candidate.is_file():
        errors.append(f"asset candidate missing after revision: {_rel(candidate, root)}")
    elif _file_sha256(candidate) == previous_hash:
        errors.append("asset candidate content did not change; review labels cannot substitute for a real revision")

    payload, error = _read_optional_json(review_json)
    if error:
        errors.append(error)
    else:
        status = str(payload.get("status") or "").strip().lower()
        if status != "recheck_required":
            errors.append(f"revised asset review status must be recheck_required; got {status or 'missing'}")
        candidate_ref = str(payload.get("candidate") or "").strip()
        if candidate_ref and Path(candidate_ref).stem != candidate_id:
            errors.append(f"asset revision candidate mismatch: {candidate_ref} does not match {candidate_id}")
        applied = payload.get("applied_revision_actions")
        if not isinstance(applied, list) or not applied:
            errors.append("revised asset review must record non-empty applied_revision_actions")
        round_value = payload.get("revision_round")
        if not isinstance(round_value, int) or isinstance(round_value, bool) or round_value < 1:
            errors.append("revised asset review must record revision_round as an integer >= 1")

    completion_payload, completion_error = _read_optional_json(completion)
    if completion_error:
        errors.append(completion_error)
    else:
        status = str(completion_payload.get("status") or "").strip().lower()
        if status != "recheck_required":
            errors.append(f"asset review completion status must be recheck_required after revision; got {status or 'missing'}")
        if completion_payload.get("expected_artifacts_checked") is not False:
            errors.append("asset review completion expected_artifacts_checked must be false until fresh review")
        expected_source = _rel(review_task, root)
        source_task = str(completion_payload.get("source_task") or "").replace("\\", "/")
        if source_task != expected_source:
            errors.append(f"asset review completion source_task must be {expected_source}")

    for path, label in ((candidate.with_suffix(".md"), "candidate report"), (review, "asset review report")):
        if not path.exists():
            errors.append(f"{label} missing: {_rel(path, root)}")
    return errors


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_approval_gate_errors(root: Path, candidate_id: str, candidate: Path) -> list[str]:
    approval = _approval_record_for_run(root, candidate_id)
    if str(approval.get("decision") or "") == "approve" and _approval_matches_file(approval, candidate):
        return []
    return [f"asset promotion requires current-content approve record for run_id {candidate_id}; got {approval.get('decision') or 'missing/stale'}"]


def _approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    if not approval or not subject.is_file():
        return False
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == _file_sha256(subject)
    recorded_at = _parse_datetime(str(approval.get("recorded_at") or ""))
    if recorded_at is None:
        return False
    subject_time = datetime.fromtimestamp(subject.stat().st_mtime, tz=timezone.utc)
    return subject_time <= recorded_at


def _asset_promotion_gate_errors(root: Path, candidate_id: str) -> list[str]:
    manifest = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    report = manifest.with_suffix(".md")
    payload, error = _read_optional_json(manifest)
    errors: list[str] = []
    if error:
        errors.append(error)
        return errors
    if payload.get("status") != "promoted":
        errors.append(f"asset promotion status must be promoted; got {payload.get('status') or 'missing'}")
    if payload.get("allow_unapproved"):
        errors.append("asset promotion used allow_unapproved; formal Skill-host route must not use approval bypass")
    if str(payload.get("candidate_id") or "") != candidate_id:
        errors.append(f"asset promotion candidate_id mismatch: {payload.get('candidate_id') or 'missing'}")
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), list) else []
    if not outputs:
        errors.append("asset promotion manifest must list outputs")
    for item in outputs:
        path = _resolve_project_path(root, str(item))
        if not path.exists():
            errors.append(f"asset promotion output missing: {_rel(path, root)}")
    if not report.exists():
        errors.append(f"asset promotion report missing: {_rel(report, root)}")
    return errors


def _asset_candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidate = str(task.get("candidate") or "").strip()
    if candidate:
        return _resolve_project_path(root, candidate)
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".json"):
            continue
        if ".agent_" in normalized or "/reviews/" in f"/{normalized}" or "/workflow/" in f"/{normalized}":
            continue
        if _is_asset_candidate_rel(normalized):
            return _resolve_project_path(root, item)
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or "asset-intake")
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def _is_asset_candidate_rel(value: str) -> bool:
    normalized = value.replace("\\", "/").lstrip("/")
    return any(normalized.startswith(folder.as_posix() + "/") for folder in ASSET_CANDIDATE_DIRS.values())


def _asset_type_from_payload_or_path(root: Path, candidate: Path, payload: dict[str, object]) -> str:
    asset_type = str(payload.get("asset_type") or "").strip().lower().replace("_", "-")
    if asset_type:
        return asset_type
    rel = _rel(candidate, root)
    for item_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix() + "/"):
            return item_type
    return ""


def _asset_promotion_group(asset_type: str) -> str:
    normalized = asset_type.strip().lower().replace("_", "-")
    for group, members in PROMOTABLE_GROUPS.items():
        if normalized in members:
            return group
    return ""


def _asset_promoted_output_rels(root: Path, candidate: Path, asset_type: str) -> list[str]:
    """Predict the formal files written by promote-candidate-asset.

    The Worker treats every undeclared write as a contract violation, so the
    deterministic promotion task must declare both its manifest and the exact
    project asset paths produced by ``asset_workshop._write_promoted_asset``.
    """

    if not candidate.is_file():
        return []
    payload = _read_json(candidate)
    normalized = asset_type.strip().lower().replace("_", "-")

    def safe_id(value: object, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", str(value or fallback).strip()).strip("_")
        return cleaned or "asset"

    if normalized == "character":
        character_id = safe_id(payload.get("character_id"), "agent_character")
        return [f"characters/{character_id}.yaml"]
    if normalized == "background-story":
        character_id = safe_id(payload.get("target_character_id"), "agent_character")
        return [f"characters/{character_id}.yaml"]
    if normalized == "relationship":
        return ["plot/relationship_graph.json"]
    if normalized == "world":
        return ["canon/world_rules.yaml"]
    if normalized == "location":
        return ["canon/locations.yaml"]
    if normalized == "organization":
        return ["canon/organizations.yaml"]

    outputs = ["plot/outline.md"]
    scene_list = payload.get("scene_list") if isinstance(payload.get("scene_list"), list) else []
    for item in scene_list:
        if not isinstance(item, dict):
            continue
        scene_id = safe_id(item.get("scene_id"), "scene_candidate")
        output = f"scenes/{scene_id}.yaml"
        if output not in outputs:
            outputs.append(output)
    return outputs


def _approval_record_for_run(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def _context_trace_gate_errors(root: Path, scene_id: str) -> list[str]:
    if not scene_id:
        return ["context task missing scene_id; cannot validate context trace"]
    context = root / "memory" / "context_packets" / f"{scene_id}.md"
    if not context.exists():
        return [f"context packet is missing: {_rel(context, root)}"]
    status = context_trace_status(root, scene_id, context)
    if not status.passed:
        return [status.message]
    return []


def _roleplay_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "branches" / scene_id / "roleplay_simulation.md"
    text = _read_text(path)
    if not text:
        return [f"roleplay simulation is empty or unreadable: {_rel(path, root)}"]
    if "正式 CLI 来源" not in text or "simulate-scene" not in text:
        return [
            "roleplay simulation lacks CLI provenance text from simulate-scene; "
            "manual RP files are exploratory/debug-only for the formal route"
        ]
    return []


def _branch_manifest_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "branches" / scene_id / "branch_manifest.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"branch manifest is missing or empty: {_rel(path, root)}"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    created_by = str(provenance.get("created_by") or "")
    if created_by != "branch-simulate":
        return [
            "branch manifest lacks formal_cli_provenance.created_by=branch-simulate; "
            "run branch-simulate --agent instead of hand-writing the manifest"
        ]
    if provenance.get("agent_tasks_requested") is not True:
        return ["branch manifest was not created with --agent; branch sidecar is required for formal route"]
    return []


def _branch_selection_gate(root: Path, scene_id: str) -> tuple[list[str], list[str]]:
    selection = root / "branches" / scene_id / "branch_selection.md"
    branch_state = branch_selection_status(selection)
    if branch_state.get("status") != "selected":
        return [str(branch_state.get("message") or "branch selection is not selected")], []
    return [], [f"branch selection: {branch_state.get('selected_branch')}"]


def _composition_gate_errors(root: Path, scene_id: str) -> list[str]:
    composition = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    try:
        payload = ensure_composition_ready_for_generation(root, composition)
    except (FlowGateError, json.JSONDecodeError, OSError, ValueError) as exc:
        return [str(exc)]
    flow_gate = payload.get("flow_gate") if isinstance(payload.get("flow_gate"), dict) else {}
    if flow_gate.get("ready_for_generation") is not True:
        return ["composition ready_for_generation must be true before prose generation"]
    provenance = payload.get("formal_cli_provenance") if isinstance(payload.get("formal_cli_provenance"), dict) else {}
    if provenance.get("agent_tasks_requested") is not True:
        return ["composition was not created with --agent-tasks; composition sidecar is required"]
    return []


def _word_budget_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_path = _scene_path_for_task(root, task)
    try:
        contract = ensure_scene_word_budget_ready(root, scene_path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]
    if contract.get("status") == "not_required":
        return []
    errors: list[str] = []
    scene_inventory_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    if scene_inventory_task.exists():
        completion = agent_task_completion_status(scene_inventory_task, root=root)
        if completion.get("complete") is not True:
            errors.append(f"scene-inventory word-budget sidecar is incomplete: {completion.get('message')}")
    scene_inventory_review = root / "reviews" / "word_budget" / "scene_inventory_review.md"
    if scene_inventory_task.exists() and not scene_inventory_review.exists():
        errors.append("formal longform scene generation requires reviews/word_budget/scene_inventory_review.md")
    return errors


def _reader_experience_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_path = _scene_path_for_task(root, task)
    try:
        contract = ensure_reader_experience_ready(root, scene_path)
    except (FileNotFoundError, ValueError) as exc:
        return [str(exc)]
    if contract.get("status") == "not_required":
        return []
    return []


def _narrative_rhythm_gate_errors(root: Path, scene_id: str) -> list[str]:
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    if not scene_path.is_file():
        return [f"scene file is missing for narrative rhythm contract: {_rel(scene_path, root)}"]
    contract = narrative_rhythm_contract(root, scene_path)
    if str(contract.get("status") or "") == "pass":
        return []
    return [f"narrative rhythm/bridge contract is not ready: {contract.get('message') or 'missing required fields'}"]


def _candidate_generation_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_generation_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    details: list[str] = [str(gate.get("message") or "candidate generation gate failed")]
    missing = gate.get("missing")
    invalid = gate.get("invalid")
    if isinstance(missing, list) and missing:
        details.append("missing=" + ", ".join(str(item) for item in missing))
    if isinstance(invalid, list) and invalid:
        details.append("invalid=" + ", ".join(str(item) for item in invalid))
    return ["; ".join(details)]


def _candidate_body_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    if not candidate.exists():
        return [f"candidate Markdown is missing: {_rel(candidate, root)}"]
    scene_path = _scene_path_for_task(root, task)
    body = final_body_from_draft_path(candidate)
    errors: list[str] = []
    if not body:
        errors.append(f"candidate has no cleaned deliverable body: {_rel(candidate, root)}")
        return errors
    scene_id = str(task.get("scene_id") or scene_path.stem)
    lint_gate = style_lint_gate(body, profile=load_creative_quality_profile(root), scope=scene_id)
    if lint_gate.get("status") == "blocking":
        errors.append(f"candidate failed Style Lint Gate: {style_lint_gate_message(lint_gate)}")
    budget = word_budget_adherence_for_body(root, scene_path, body)
    if budget.get("status") not in {"pass", "not_required"}:
        errors.append(f"candidate failed scene word-budget gate: {budget.get('message')}")
    reader = reader_experience_adherence_for_body(root, scene_path, body)
    if reader.get("status") not in {"pass", "not_required"}:
        errors.append(f"candidate failed reader-experience gate: {reader.get('message')}")
    return errors


def _candidate_review_gate_errors(
    root: Path,
    task: dict[str, object],
    candidate: Path,
    *,
    require_pass: bool = True,
) -> list[str]:
    scene_id = str(task.get("scene_id") or candidate.stem.split("-")[0])
    gate = candidate_review_gate(root, scene_id, candidate)
    if gate.get("status") == "pass":
        return []
    if not require_pass:
        infrastructure_failures = {
            "schema_failed",
            "task_incomplete",
            "stale_or_wrong_source",
            "creative_quality_review_stale",
        }
        if str(gate.get("status") or "") not in infrastructure_failures:
            return []
    message = str(gate.get("message") or "candidate review gate failed")
    lint_gate = gate.get("style_lint")
    if isinstance(lint_gate, dict) and lint_gate.get("status") == "blocking":
        message += f"; Style Lint Gate: {style_lint_gate_message(lint_gate)}"
    return [message]


def _scene_revision_gate_errors(root: Path, task: dict[str, object], candidate: Path) -> list[str]:
    errors: list[str] = []
    source_rel = str(task.get("revision_source") or "").strip()
    previous_hash = str(task.get("candidate_sha256_before_revision") or "").strip().lower()
    if not source_rel or not previous_hash:
        errors.append("scene revision task is missing exact source candidate hash provenance")
    elif not candidate.is_file():
        errors.append(f"scene revision candidate is missing: {_rel(candidate, root)}")
    elif _file_sha256(candidate) == previous_hash:
        errors.append("scene revision candidate is unchanged from the exact reviewed source")

    scene_id = str(task.get("scene_id") or candidate.stem.replace("_revision", ""))
    base = root / "drafts" / "revisions" / f"{scene_id}_revision"
    manifest_path = base.with_suffix(".json")
    report = base.with_name(base.name + "_report.md")
    prompt = base.with_suffix(".prompt.json")
    sidecar = base.with_suffix(".agent_tasks.md")
    completion = default_agent_completion_path(sidecar)
    for path, label in ((report, "revision report"), (prompt, "revision prompt manifest"), (sidecar, "revision sidecar")):
        if not path.is_file():
            errors.append(f"{label} missing: {_rel(path, root)}")
    payload, error = _read_optional_json(manifest_path)
    if error:
        errors.append(error)
    else:
        if payload.get("schema") != "literary-engineering-workbench/scene-revision/v0.1":
            errors.append("scene revision manifest has wrong or missing schema")
        if str(payload.get("scene_id") or "") != scene_id:
            errors.append(f"scene revision manifest scene_id mismatch: {payload.get('scene_id') or 'missing'}")
        if payload.get("ready_for_review") is not False:
            errors.append("scene revision manifest ready_for_review must remain false until independent AgentReview")
        if payload.get("anti_evasion_protocol_applied") is not True:
            errors.append("scene revision manifest must record anti_evasion_protocol_applied=true")
        applied_fields = ("revision_actions_applied", "warnings_addressed", "style_notes_addressed", "style_adherence_addressed")
        if not any(payload.get(field) for field in applied_fields):
            errors.append("scene revision manifest must record at least one applied review repair")
        unresolved = payload.get("evasion_risks_unresolved")
        if unresolved not in (None, False, "", [], {}):
            errors.append("scene revision manifest has unresolved anti-evasion risks")
    completion_state = agent_task_completion_status(sidecar, root=root)
    if completion_state.get("complete") is not True:
        errors.append(f"scene revision sidecar is incomplete: {completion_state.get('message')}")
    return errors


def _promotion_gate_errors(root: Path, task: dict[str, object]) -> list[str]:
    scene_id = str(task.get("scene_id") or "")
    manifest_path = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    payload, error = _read_optional_json(manifest_path)
    if error:
        return [error]
    if not payload:
        return [f"promotion manifest is missing or empty: {_rel(manifest_path, root)}"]
    errors: list[str] = []
    if payload.get("allow_unreviewed") is True:
        errors.append("promotion manifest uses allow_unreviewed=true; debug review bypass is forbidden for formal Skill hosts")
    if payload.get("allow_review_notes") is True:
        errors.append("promotion manifest uses allow_review_notes=true; pass_with_notes must be revised and re-reviewed")
    candidate_value = str(payload.get("candidate") or "")
    if not candidate_value:
        errors.append("promotion manifest does not record candidate path")
        return errors
    candidate = _resolve_project_path(root, candidate_value)
    errors.extend(_candidate_generation_gate_errors(root, task, candidate))
    errors.extend(_candidate_review_gate_errors(root, task, candidate))
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if draft.exists() and not final_body_from_draft_path(draft):
        errors.append(f"promoted draft has no cleaned deliverable body: {_rel(draft, root)}")
    return errors


def _static_review_gate_errors(root: Path, scene_id: str, *, require_pass: bool = True) -> list[str]:
    path = root / "reviews" / f"{scene_id}-review.md"
    conclusion = _static_review_conclusion(path)
    allowed = {"pass", "pass_with_notes", "revise_required", "reject"}
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if conclusion not in allowed:
        return [f"static review conclusion must be recorded; got {conclusion or 'missing'} at {_rel(path, root)}"]
    if not _static_review_matches_draft(path, draft):
        return [f"static review is stale for current promoted draft at {_rel(path, root)}"]
    if not require_pass or conclusion == "pass":
        return []
    return [f"static review conclusion must be pass; got {conclusion or 'missing'} at {_rel(path, root)}"]


def _static_review_matches_draft(review: Path, draft: Path) -> bool:
    if not review.is_file() or not draft.is_file():
        return False
    match = re.search(r"(?m)^-\s*审查对象 SHA-256：`([0-9a-fA-F]{64})`\s*$", _read_text(review))
    return bool(match and match.group(1).lower() == _file_sha256(draft))


def _state_patch_gate_errors(root: Path, scene_id: str) -> list[str]:
    path = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    payload, error = _read_optional_json(path)
    if error:
        return [error]
    if not payload:
        return [f"state patch JSON is missing or empty: {_rel(path, root)}"]
    errors: list[str] = []
    if str(payload.get("schema") or "") != "literary-engineering-workbench/character-state-patch/v0.1":
        errors.append("state patch JSON has wrong or missing schema")
    if str(payload.get("scene_id") or "") not in {"", scene_id}:
        errors.append(f"state patch scene_id mismatch: {payload.get('scene_id')}")
    if str(payload.get("status") or "").strip().lower() not in {"pending_human_approval", "candidate", "reviewed", "approved"}:
        errors.append("state patch status must remain candidate/review/approval-scoped")
    return errors


def _canon_writeback_gate_errors(root: Path, scene_id: str) -> list[str]:
    status = canon_writeback_status(root, scene_id)
    state = str(status.get("status") or "")
    if state in {"pass", "not_required"}:
        return []
    return [f"canon writeback gate is not complete for {scene_id}: {status.get('message')}"]


def _candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".md"):
            continue
        if normalized.endswith(".agent_tasks.md") or normalized.endswith(".prompt.md"):
            continue
        if "/drafts/candidates/" in f"/{normalized}" or "/drafts/revisions/" in f"/{normalized}":
            return _resolve_project_path(root, item)
    scene_id = str(task.get("scene_id") or "scene")
    return root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"


def _scene_path_for_task(root: Path, task: dict[str, object]) -> Path:
    scene = str(task.get("scene") or "")
    if scene:
        return _resolve_project_path(root, scene)
    scene_id = str(task.get("scene_id") or "scene_0001")
    return root / "scenes" / f"{scene_id}.yaml"


def _static_review_conclusion(path: Path) -> str:
    text = _read_text(path)
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {_rel(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _context_source_paths(root: Path, scene_rel: str) -> list[str]:
    hard_context = [
        "project.yaml",
        scene_rel,
        "canon",
        "characters",
        "plot/outline.md",
        "plot/foreshadowing.csv",
        "plot/conflict_matrix.md",
        "plot/word_budget/word_budget.json",
        "plot/word_budget/word_budget.md",
        "plot/chapter_obligations",
        "plot/rhythm_plan.json",
        # A materialized scene inventory turns a provisional expansion budget
        # into a formal, executable per-scene contract. Generation commands
        # run in task sandboxes, so this proof must travel with every scene
        # task rather than remain visible only at the project root.
        "workflow/longform_materialization.json",
        "style",
    ]
    index = root / "memory" / "index.json"
    if index.is_file():
        hard_context.append("memory/index.json")
    else:
        hard_context.extend(["sources", "scenes", "drafts/scenes", "reviews/agent"])
    return [rel for rel in dict.fromkeys(hard_context) if (root / rel).exists()]


def _load_task(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"task not found: {path}")
    payload = _read_json(path)
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"not an agent task registry file: {path}")
    return payload


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def _append_event(root: Path, event_type: str, task_id: str, data: dict[str, object]) -> None:
    path = _events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": EVENT_SCHEMA,
        "event_type": event_type,
        "task_id": task_id,
        "created_at": _now(),
        "data": data,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {"schema": EVENT_SCHEMA, "event_type": "invalid", "task_id": "", "created_at": "", "data": {"raw": line}}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _render_events_markdown(events: list[dict[str, object]]) -> str:
    lines = [
        "# Workflow Events",
        "",
        f"- events: {len(events)}",
        "",
        "| 时间 | 事件 | task_id | 数据 |",
        "| --- | --- | --- | --- |",
    ]
    for event in events:
        data = json.dumps(event.get("data") or {}, ensure_ascii=False)
        lines.append(f"| {event.get('created_at', '')} | {event.get('event_type', '')} | {event.get('task_id', '')} | `{data}` |")
    return "\n".join(lines).rstrip() + "\n"


def _task_json_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.task.json"


def _task_markdown_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.agent_tasks.md"


def _submission_path(root: Path, task_id: str) -> Path:
    return root / "workflow" / "tasks" / f"{task_id}.submission.json"


def _events_path(root: Path) -> Path:
    return root / "workflow" / "events" / "task_events.jsonl"


def _task_id(route: str, scene_id: str, current_state: str) -> str:
    return _slug(f"{route}__{scene_id}__{current_state}")


def _slug(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "task"


def _resolve_project_path(root: Path, value: Path | str) -> Path:
    path = value if isinstance(value, Path) else Path(str(value))
    return path if path.is_absolute() else root / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _normalize_rel(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def _project_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")


def _project_int(text: str, key: str) -> int:
    return _to_int(_project_scalar(text, key))


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
