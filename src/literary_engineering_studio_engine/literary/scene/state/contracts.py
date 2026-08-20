"""Value contracts for character-state candidate construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CharacterStatePatchResult:
    project_root: Path
    output_path: Path
    json_path: Path
    agent_tasks_path: Path | None
    scene_id: str
    source_path: Path
    character_count: int
    unresolved_count: int


@dataclass(frozen=True)
class StatePatchSources:
    root: Path
    scene_path: Path
    scene_id: str
    participants: tuple[str, ...]
    source_path: Path
    source_text: str


__all__ = ["CharacterStatePatchResult", "StatePatchSources"]
