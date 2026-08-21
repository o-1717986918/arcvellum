"""Workflow projection for one scene's whole-work length repair allocation."""

from __future__ import annotations

from pathlib import Path

from ..foundation.draft_text import (
    count_delivery_chinese_content_chars,
    final_body_from_draft_path,
)
from ..literary.planning.length_repair import scene_length_repair_allocation
from .state_common import _rel


def target_length_revision_step(
    root: Path,
    scene_id: str,
    candidate: Path | None,
) -> dict[str, object]:
    allocation = scene_length_repair_allocation(root, scene_id)
    if not allocation:
        return _closed_step()
    minimum = int(allocation.get("minimum_scene_chars") or 0)
    actual = _candidate_chars(candidate)
    if actual >= minimum:
        return {
            "key": "target-length-gate",
            "status": "pass",
            "path": _rel(candidate, root) if candidate is not None else "",
            "message": f"revision candidate chars={actual}; required={minimum}",
            "next_action": "",
        }
    return {
        "key": "target-length-revision",
        "status": "needs_revision",
        "path": "reviews/longform/target_length_repair.json",
        "message": (
            f"whole-work repair allocation remains open for {scene_id}: "
            f"candidate chars={actual}; required={minimum}; "
            f"net growth={int(allocation.get('required_growth_chars') or 0)}"
        ),
        "next_action": (
            "revise the exact promoted scene through the target-length repair task; "
            "add only causal, relational, informational, or earned aftermath content"
        ),
    }


def _closed_step() -> dict[str, object]:
    return {
        "key": "target-length-gate",
        "status": "pass",
        "path": "reviews/longform/target_length_repair.json",
        "message": "scene has no pending whole-work length allocation",
        "next_action": "",
    }


def _candidate_chars(candidate: Path | None) -> int:
    if candidate is None or not candidate.is_file():
        return 0
    return count_delivery_chinese_content_chars(final_body_from_draft_path(candidate))


__all__ = ["target_length_revision_step"]
