"""Workflow projections for scene-level character-state writeback."""
from __future__ import annotations

from pathlib import Path

from ..canon_evolver import canon_writeback_status
from ..character_state_apply import state_patch_writeback_status
from ..scene_handoff import scene_handoff_source_status
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


def canon_writeback_step(root: Path, scene_id: str) -> dict[str, object]:
    status = canon_writeback_status(root, scene_id)
    state = str(status.get("status") or "")
    passed = state in {"pass", "not_required"}
    key, next_action = _canon_route(state, passed)
    return {
        "key": key,
        "display_key": "canon-writeback",
        "status": "pass" if passed else state or "unknown",
        "path": status.get("json", ""),
        "message": status.get("message", ""),
        "patch_id": status.get("patch_id", ""),
        "candidate_sha256": status.get("candidate_sha256", ""),
        "approval_decision": status.get("approval_decision", ""),
        "next_action": next_action,
    }


def scene_handoff_step(root: Path, scene_id: str) -> dict[str, object]:
    passed, message, _payload = scene_handoff_source_status(root, scene_id)
    return {
        "key": "scene-handoff",
        "status": "pass" if passed else "missing",
        "path": f"workflow/handoffs/{scene_id}.json",
        "message": message,
        "next_action": "" if passed else f"run scene-handoff for scenes/{scene_id}.yaml",
    }


def _canon_route(state: str, passed: bool) -> tuple[str, str]:
    if passed:
        return "canon-writeback", ""
    return {
        "task_incomplete": ("canon-agent-task", "complete the exact-digest Canon semantic review"),
        "semantic_incomplete": ("canon-agent-task", "complete the exact-digest Canon semantic review"),
        "needs_approval": ("canon-patch-approval", "record a content-bound Canon patch decision"),
        "pending_apply": ("canon-patch-apply", "apply the exact approved Canon patch before continuing"),
        "needs_revision": ("canon-patch-revision", "reconcile the Canon candidate with the decision and request fresh review"),
        "rejected": ("canon-patch-revision", "reconcile the Canon candidate with the decision and request fresh review"),
        "deferred": ("canon-patch-deferred", "resume the deferred Canon decision before chronological scene work continues"),
    }.get(
        state,
        (
            "canon-patch-json",
            "run canon-evolve, have the platform agent write canon patch/no-change rationale, then complete the sidecar",
        ),
    )


__all__ = ["canon_writeback_step", "scene_handoff_step", "state_patch_review_step"]
