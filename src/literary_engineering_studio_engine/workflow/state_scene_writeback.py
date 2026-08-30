"""Workflow projections for scene-level character-state writeback."""
from __future__ import annotations

from pathlib import Path

from ..character_state_apply import state_patch_writeback_status
from .state_common import _semantic_task_step


def state_patch_review_step(root: Path, scene_id: str) -> dict[str, object]:
    """Skip semantic review when no durable character-state mutation exists."""

    value = str(state_patch_writeback_status(root, scene_id).get("status") or "")
    if value in {"not_required", "needs_revision", "stale_source"}:
        message = (
            "state semantic review is not required for an empty patch"
            if value == "not_required"
            else "state semantic review deferred until the patch contract is rebuilt"
        )
        return {
            "key": "state-agent-task",
            "status": "pass",
            "path": f"characters/state_patches/{scene_id}_state_patch.agent_tasks.md",
            "message": message,
            "next_action": "",
        }
    return _semantic_task_step(
        "state-agent-task",
        root,
        scene_id,
        root / "characters" / "state_patches" / f"{scene_id}_state_patch.agent_tasks.md",
        "complete the state semantic review and sidecar marker",
    )
