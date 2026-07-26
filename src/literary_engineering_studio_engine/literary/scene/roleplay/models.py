"""Roleplay domain records shared by simulation and downstream scene services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CharacterCard:
    file: Path
    character_id: str
    name: str
    role: str
    belief: list[str]
    desire: list[str]
    intention: list[str]
    fear: list[str]
    secret: list[str]
    background_summary: str
    formative_events: list[str]
    behavior_influences: list[str]
    reveal_policy: str
    moral_line: str
    speech_style: str


@dataclass(frozen=True)
class SimulationResult:
    project_root: Path
    output_path: Path
    context_path: Path
    scene_id: str
    character_count: int
    agent_tasks_path: Path | None = None
