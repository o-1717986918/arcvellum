"""Read-only readiness projection used by chapter assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..scene.promotion.historical_readiness import historical_scene_readiness
from ..scene.promotion.readiness import (
    agent_review_gate_state,
    scene_flow_gate_issues,
    scene_readiness_status,
)


def chapter_scene_readiness(
    root: Path,
    scene_id: str,
    *,
    draft_path: Path,
    review_path: Path,
    agent_review_json_path: Path,
    body: str,
    static_review_conclusion: str,
) -> tuple[tuple[str, ...], dict[str, Any], str, tuple[str, ...]]:
    """Project one scene through sealed-history or current-policy readiness."""

    historical = historical_scene_readiness(root, scene_id)
    flow_issues = () if historical is not None else scene_flow_gate_issues(
        root,
        scene_id,
    )
    agent_state = agent_review_gate_state(
        root,
        agent_review_json_path,
        draft_path,
    )
    if historical is not None:
        status, readiness_issues = historical
    else:
        status, readiness_issues = scene_readiness_status(
            root,
            draft_path=draft_path,
            review_path=review_path,
            agent_review_json_path=agent_review_json_path,
            body=body,
            static_review_conclusion=static_review_conclusion,
            flow_gate_issues=flow_issues,
            agent_review_state=agent_state,
        )
    return flow_issues, agent_state, status, readiness_issues


__all__ = ["chapter_scene_readiness"]
