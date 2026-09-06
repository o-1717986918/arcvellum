"""Stable result and scene-record contracts for chapter assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneChapterRecord:
    scene_id: str
    scene_path: str
    chapter_id: str
    location: str
    participants: tuple[str, ...]
    scene_goal: str
    context_path: str
    context_trace_path: str
    simulation_path: str
    draft_path: str
    review_path: str
    review_conclusion: str
    agent_review_path: str
    agent_review_json: str
    agent_review_validation: str
    agent_review_conclusion: str
    agent_review_schema_status: str
    agent_review_source_match: bool
    agent_review_unresolved_notes: tuple[str, ...]
    style_adherence_status: str
    word_budget_adherence_status: str
    reader_experience_adherence_status: str
    reader_promise_satisfied: bool
    narrative_rhythm_status: str
    rhythm_role: str
    pace: str
    tension_curve: object
    scene_function: tuple[str, ...]
    scene_turn: str
    reader_effect: str
    incoming_pressure: str
    outgoing_hook: str
    flow_gate_issues: tuple[str, ...]
    readiness_issues: tuple[str, ...]
    draft_chars: int
    draft_machine_chars: int
    status: str
    writeback_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ChapterWorkspaceResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    chapter_id: str
    scene_count: int
    ready_count: int
    blocked_count: int


__all__ = ["ChapterWorkspaceResult", "SceneChapterRecord"]
