"""TaskPackage assembly for the project review route."""

from __future__ import annotations

from pathlib import Path

from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    resolve_project_path as _resolve_project_path,
    task_id as _task_id,
)
from .blueprints import review_audit_blueprint_for_state
from .evidence import file_sha256, unique


DEFAULT_REQUIRED_READING = [
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
]

FORBIDDEN_SHORTCUTS = [
    "Do not treat canon-lint or longform-audit as a semantic review by themselves.",
    "Do not use local dry-run/http-chat provider output as the formal review judgment.",
    "Do not let review pass_with_notes, unresolved facts, timeline risks, committee action_items, or disagreements move into export/release.",
    "A semantic review task must not edit project sources. A formal revision task may edit only its exact declared repair_targets inside the isolated sandbox.",
    "Do not treat this task as complete until task-submit and task-complete have succeeded.",
]


def build_review_audit_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = review_audit_blueprint_for_state(root, current_state, next_action, state)
    target_id = str(state.get("patch_id") or "project-review")
    task_id = _task_id(route, target_id, current_state)
    expected_outputs = unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    payload = _base_payload(
        route=route,
        state=state,
        blueprint=blueprint,
        task_id=task_id,
        target_id=target_id,
        current_state=current_state,
        source_paths=source_paths,
        expected_outputs=expected_outputs,
    )
    _attach_repair_provenance(root, payload, blueprint)
    return payload


def _base_payload(
    *,
    route: str,
    state: dict[str, object],
    blueprint: dict[str, object],
    task_id: str,
    target_id: str,
    current_state: str,
    source_paths: list[str],
    expected_outputs: list[str],
) -> dict[str, object]:
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": _now(),
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
        "required_reading": list(blueprint.get("required_reading", DEFAULT_REQUIRED_READING)),
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
        "forbidden_shortcuts": FORBIDDEN_SHORTCUTS.copy(),
        "next_allowed_states": blueprint["next_allowed_states"],
    }


def _attach_repair_provenance(
    root: Path,
    payload: dict[str, object],
    blueprint: dict[str, object],
) -> None:
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if not repair_targets:
        return
    payload["repair_targets"] = repair_targets
    payload["repair_target_sha256_before_revision"] = {
        relative: file_sha256(_resolve_project_path(root, relative))
        for relative in repair_targets
        if _resolve_project_path(root, relative).is_file()
    }
