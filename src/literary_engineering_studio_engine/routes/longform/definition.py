"""Composition surface for the longform-planning route.

Blueprint construction and Gate validation live in focused sibling modules so
callers keep one stable route API without coupling to implementation details.
"""

from __future__ import annotations

from pathlib import Path

from ...semantic_task_contracts import semantic_artifact_contract
from ...tasking.builder import TaskBuilder, WordCountContract
from .blueprints import blueprint_for_state
from .context_policy import agent_context_payload
from .gates import repair_targets_changed, validate_task, word_budget_file_gate_errors


DEFAULT_REQUIRED_READING = [
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "references/agent-run-protocol.md",
    "references/cli-run-protocol.md",
    "docs/modules/longform-word-budget.md",
]

FORBIDDEN_SHORTCUTS = [
    "Do not treat word_budget.json as final plot or sufficient narrative inventory by itself.",
    "Do not bypass the semantic requirements compiled into the current budget, scene-inventory, or chapter-obligation task package.",
    "Do not start bulk scene generation while longform-planning is blocked.",
    "Do not satisfy target length by making each scene verbose; expand narrative inventory instead.",
    "Do not overwrite formal plot/outline.md or scenes/ before candidate review and user approval.",
    "Do not treat this task as complete until task-submit and task-complete have succeeded.",
]


def build_task_payload(root: Path, route: str, state: dict[str, object]) -> dict[str, object]:
    current_state = str(state.get("current_step") or "")
    next_action = str(state.get("next_action") or "")
    blueprint = blueprint_for_state(root, current_state, next_action)
    payload = TaskBuilder(
        root=root,
        route=route,
        target_id="longform",
        scene_id="longform",
        current_state=current_state,
        blueprint=blueprint,
        required_reading=DEFAULT_REQUIRED_READING,
        forbidden_shortcuts=FORBIDDEN_SHORTCUTS,
        route_fields={"scene": "project.yaml"},
        word_count=WordCountContract(
            blueprint.get("word_count_target", 0),
            blueprint.get("word_count_min", 0),
            blueprint.get("word_count_max", 0),
        ),
    ).build()
    payload.update(agent_context_payload(blueprint))
    semantic = semantic_artifact_contract(current_state, "longform")
    if semantic is not None:
        payload["semantic_artifact"] = semantic
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
