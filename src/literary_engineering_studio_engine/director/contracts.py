"""Stable value objects and schema constants for the creative director."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..model_config import MODEL_PROVIDER_CHOICES

DIRECTOR_SCHEMA = "director_decision.v1"
DIRECTOR_SCHEMA_VALUE = "literary-engineering-workbench/director-decision/v0.1"
DIRECTOR_WORKFLOWS = {"project-seeding", "character-lab", "worldbuilding-lab", "outline-lab", "scene-loop"}
DIRECTOR_PROVIDERS = MODEL_PROVIDER_CHOICES
DIRECTOR_CONVERSATION_SCHEMA = "literary-engineering-workbench/director-conversation-turn/v0.1"
DIRECTOR_TOOL_LOOP_SCHEMA = "literary-engineering-workbench/director-tool-loop/v0.1"
DIRECTOR_MAX_TOOL_STEPS = 5
DIRECTOR_ALLOWED_TOOLS = {
    "init_project",
    "record_project_direction",
    "run_workflow",
    "create_asset_candidate",
    "review_candidates",
    "summarize_project_status",
    "ask_user",
    "write_director_report",
}


@dataclass(frozen=True)
class DirectorTurnResult:
    project_root: Path
    run_id: str
    status: str
    reply: str
    decision_path: Path
    report_path: Path
    agent_run_dir: Path
    validation_path: Path
    workflow_state_path: Path | None
    action: str
    artifacts: dict[str, str]
    decision: dict[str, Any]


@dataclass(frozen=True)
class DirectorBootstrapResult:
    root: Path
    title: str
    files: tuple[Path, ...]
    bootstrap_path: Path


@dataclass(frozen=True)
class DirectorToolLoopResult:
    path: Path
    status: str
    steps: list[dict[str, Any]]
    workflow_result: Any
    workflow_error: str
    artifacts: dict[str, str]
