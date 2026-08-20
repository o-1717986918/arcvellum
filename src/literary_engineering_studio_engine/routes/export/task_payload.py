"""TaskPackage assembly for export and release work."""

from __future__ import annotations

from pathlib import Path

from ...task_paths import (
    TASK_SCHEMA,
    normalize_relative_path as _normalize_rel,
    now as _now,
    task_id as _task_id,
)
from .blueprints import export_release_blueprint_for_state
from .evidence import unique


DEFAULT_REQUIRED_READING = [
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
]

FORBIDDEN_SHORTCUTS = [
    "Do not use --include-blocked, --allow-unapproved, or custom export scripts for formal delivery.",
    "Do not export chapters with non-ready scenes, unresolved review notes, pending sidecars, skipped scenes, or workflow traces.",
    "Do not include scene ids, canon notes, review text, state patches, AGENT_TASK markers, or writeback candidates in final delivery files.",
    "Do not publish without a human approve record matching the release run id.",
    "Do not treat this task as complete until task-submit and task-complete have succeeded.",
]


def build_export_release_task_payload(
    root: Path,
    route: str,
    state: dict[str, object],
) -> dict[str, object]:
    chapter_id = str(state.get("chapter_id") or state.get("target_id") or "chapter_0001")
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = export_release_blueprint_for_state(root, chapter_id, current_state, next_action)
    task_id = _task_id(route, chapter_id, current_state)
    expected_outputs = unique([_normalize_rel(item) for item in blueprint["expected_outputs"]])
    source_paths = unique([_normalize_rel(item) for item in blueprint["source_paths"]])
    return {
        "schema": TASK_SCHEMA,
        "task_id": task_id,
        "status": "issued",
        "created_at": _now(),
        "route": route,
        "scene_id": chapter_id,
        "target_id": chapter_id,
        "chapter_id": chapter_id,
        "current_state": current_state,
        "task_type": blueprint["task_type"],
        "prompt_asset_id": blueprint["prompt_asset_id"],
        "command": blueprint["command"],
        "required_reading": list(blueprint.get("required_reading", DEFAULT_REQUIRED_READING)),
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
        "forbidden_shortcuts": FORBIDDEN_SHORTCUTS.copy(),
        "next_allowed_states": blueprint["next_allowed_states"],
    }


__all__ = ["build_export_release_task_payload"]
