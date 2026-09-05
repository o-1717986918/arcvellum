"""TaskPackage assembly for export and release work."""

from __future__ import annotations

from pathlib import Path

from ...tasking.builder import TaskBuilder, WordCountContract
from .blueprints import export_release_blueprint_for_state


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
    return TaskBuilder(
        root=root,
        route=route,
        target_id=chapter_id,
        scene_id=chapter_id,
        current_state=current_state,
        blueprint=blueprint,
        required_reading=DEFAULT_REQUIRED_READING,
        forbidden_shortcuts=FORBIDDEN_SHORTCUTS,
        route_fields={"chapter_id": chapter_id},
        word_count=WordCountContract(target=blueprint.get("word_count_target", 0)),
    ).build()


__all__ = ["build_export_release_task_payload"]
