"""Stable task-state groups shared by Engine and Studio adapters."""

from __future__ import annotations


SCENE_REVISION_STATES = frozenset(
    {
        "candidate-revision",
        "static-revision",
        "target-length-revision",
    }
)
SCENE_CANDIDATE_STATES = frozenset({
    "candidate-generation-provenance",
    "generation-agent-task",
    *SCENE_REVISION_STATES,
})


__all__ = ["SCENE_CANDIDATE_STATES", "SCENE_REVISION_STATES"]
