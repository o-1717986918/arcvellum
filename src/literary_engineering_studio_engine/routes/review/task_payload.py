"""TaskPackage assembly for the project review route."""

from __future__ import annotations

from pathlib import Path

from ...tasking.builder import TaskBuilder
from ...tasking.context_contract import CONTEXT_CONTRACT_SCHEMA
from .blueprints import review_audit_blueprint_for_state
from .evidence import unique


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
    payload = TaskBuilder(
        root=root,
        route=route,
        target_id=target_id,
        scene_id=str(state.get("scene_id") or "project-review"),
        current_state=current_state,
        blueprint=blueprint,
        required_reading=DEFAULT_REQUIRED_READING,
        forbidden_shortcuts=FORBIDDEN_SHORTCUTS,
        route_fields={
            "patch": str(state.get("patch") or ""),
            "patch_id": str(state.get("patch_id") or ""),
            "candidate_sha256": str(state.get("candidate_sha256") or ""),
        },
    ).build()
    _attach_repair_context_contract(payload, blueprint)
    return payload


def _attach_repair_context_contract(
    payload: dict[str, object],
    blueprint: dict[str, object],
) -> None:
    """Keep exact repair evidence available without replaying it all inline."""

    targets = unique([str(item) for item in blueprint.get("repair_targets", [])])
    if not targets:
        return
    sources = unique([str(item) for item in payload.get("source_paths", [])])
    primary_review = next(
        (
            item
            for item in sources
            if item.startswith("reviews/agent/") and item.endswith(".json")
        ),
        "",
    )
    if not primary_review:
        return
    agent_sources = unique(
        [
            primary_review,
            *(
                item
                for item in sources
                if item.endswith(".json") and item != primary_review
            ),
            *targets,
        ]
    )
    payload.update(
        {
            "agent_source_paths": agent_sources,
            "context_contract_required": True,
            "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
            "context_contract_revision": "project-review-revision-v1",
            "context_contract_status": "bounded-ready",
            "context_must_inline_paths": [primary_review],
            "context_exact_on_demand_paths": [
                item for item in agent_sources if item != primary_review
            ],
        }
    )
