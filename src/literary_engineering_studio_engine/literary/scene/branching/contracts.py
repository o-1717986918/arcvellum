"""Value contracts for scene branch simulation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....roleplay_lab import CharacterCard
from ..facts import SceneFacts


SCORE_KEYS = (
    "character_logic",
    "canon_safety",
    "dramatic_tension",
    "literary_potential",
    "longterm_payoff",
)


@dataclass(frozen=True)
class BranchCandidate:
    branch_id: str
    title: str
    strategy: str
    premise: str
    action_chain: list[str]
    character_tests: list[str]
    canon_checks: list[str]
    risks: list[str]
    writeback_candidates: dict[str, list[str]]
    scores: dict[str, int]
    total_score: int
    status: str


@dataclass(frozen=True)
class BranchSimulationResult:
    project_root: Path
    output_path: Path
    manifest_path: Path
    selection_path: Path
    agent_tasks_path: Path | None
    context_path: Path
    scene_id: str
    branch_count: int
    recommended_branch: str


@dataclass(frozen=True)
class BranchBuildContext:
    root: Path
    scene_path: Path
    scene_facts: SceneFacts
    context_path: Path
    roleplay_result: dict[str, object]
    all_cards: list[CharacterCard]
    active_cards: list[CharacterCard]


__all__ = [
    "BranchBuildContext",
    "BranchCandidate",
    "BranchSimulationResult",
    "SCORE_KEYS",
]
