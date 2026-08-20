"""Value contracts for scene composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....roleplay_lab import CharacterCard
from ..facts import SceneFacts


@dataclass(frozen=True)
class SceneCompositionResult:
    project_root: Path
    output_path: Path
    json_path: Path
    agent_tasks_path: Path | None
    context_path: Path
    context_trace_path: Path
    scene_id: str
    selected_branch: str
    character_count: int
    beat_count: int


@dataclass(frozen=True)
class SceneCompositionSources:
    root: Path
    scene_path: Path
    facts: SceneFacts
    context_path: Path
    context_trace_path: Path
    all_cards: list[CharacterCard]
    active_cards: list[CharacterCard]
    branch: dict[str, Any]

    @property
    def writing_cards(self) -> list[CharacterCard]:
        return self.active_cards or self.all_cards


__all__ = ["SceneCompositionResult", "SceneCompositionSources"]
