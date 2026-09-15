"""Compact workflow projection for a completed Lean v2 scene transaction."""

from __future__ import annotations

from pathlib import Path

from ..literary.scene.promotion.historical_readiness import lean_scene_readiness


def build_lean_scene_state(
    root: Path,
    scene_id: str,
    scene_relative: str,
) -> dict[str, object] | None:
    readiness = lean_scene_readiness(root, scene_id)
    if readiness is None:
        return None
    status, issues = readiness
    ready = status == "ready"
    next_action = "" if ready else "resume or rerun the lean scene transaction"
    step = {
        "key": "lean-scene-commit",
        "status": "pass" if ready else status,
        "path": f"workflow/scene_commits/{scene_id}.json",
        "message": (
            "exact lean-v2 scene commit is ready"
            if ready
            else "; ".join(issues) or f"lean-v2 scene commit is {status}"
        ),
        "next_action": next_action,
    }
    return {
        "scene_id": scene_id,
        "scene": scene_relative,
        "status": "ready" if ready else "blocked",
        "current_step": "ready" if ready else "lean-scene-commit",
        "next_action": next_action,
        "steps": [step],
    }


__all__ = ["build_lean_scene_state"]
