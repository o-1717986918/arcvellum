"""Composition surface for the longform-planning route.

Blueprint construction and Gate validation live in focused sibling modules so
callers keep one stable route API without coupling to implementation details.
"""

from __future__ import annotations

from pathlib import Path

from ...task_paths import TASK_SCHEMA, normalize_relative_path, now, resolve_project_path, task_id
from .blueprints import blueprint_for_state
from .context_policy import agent_context_payload
from .gates import repair_targets_changed, validate_task, word_budget_file_gate_errors
from .support import file_sha256, unique


def build_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = blueprint_for_state(root, current_state, next_action)
    identifier = task_id(route, "longform", current_state)
    expected_outputs = unique(
        [normalize_relative_path(item) for item in blueprint["expected_outputs"]]
    )
    source_paths = unique(
        [normalize_relative_path(item) for item in blueprint["source_paths"]]
    )
    payload: dict[str, object] = {
        "schema": TASK_SCHEMA,
        "task_id": identifier,
        "status": "issued",
        "created_at": now(),
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
        "submission_command": (
            "python -m literary_engineering_studio_engine task-submit <project> "
            f"--task-id {identifier} --from <artifact>"
        ),
        "completion_command": (
            "python -m literary_engineering_studio_engine task-complete <project> "
            f"--task-id {identifier}"
        ),
        "validation_gates": blueprint["validation_gates"],
        "forbidden_shortcuts": [
            "Do not treat word_budget.json as final plot or sufficient narrative inventory by itself.",
            "Do not bypass the semantic requirements compiled into the current budget, scene-inventory, or chapter-obligation task package.",
            "Do not start bulk scene generation while longform-planning is blocked.",
            "Do not satisfy target length by making each scene verbose; expand narrative inventory instead.",
            "Do not overwrite formal plot/outline.md or scenes/ before candidate review and user approval.",
            "Do not treat this task as complete until task-submit and task-complete have succeeded.",
        ],
        "next_allowed_states": blueprint["next_allowed_states"],
    }
    payload.update(agent_context_payload(blueprint))
    repair_targets = [str(item) for item in blueprint.get("repair_targets", [])]
    if repair_targets:
        payload["repair_targets"] = repair_targets
        payload["repair_target_sha256_before_revision"] = {
            relative: file_sha256(resolve_project_path(root, relative))
            for relative in repair_targets
            if resolve_project_path(root, relative).is_file()
        }
    return payload


__all__ = [
    "_repair_targets_changed",
    "blueprint_for_state",
    "build_task_payload",
    "validate_task",
    "word_budget_file_gate_errors",
]


# Compatibility for the public legacy route shim. New route code imports the
# descriptive name directly from gates.py.
_repair_targets_changed = repair_targets_changed
