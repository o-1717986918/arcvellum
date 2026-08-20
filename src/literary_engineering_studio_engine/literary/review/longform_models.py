"""Value contracts shared by long-form audit stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LongformSceneRecord:
    scene_id: str
    volume_id: str
    chapter_id: str
    scene_path: str
    location: str
    participants: tuple[str, ...]
    viewpoint: str
    scene_goal: str
    draft_path: str
    review_path: str
    review_conclusion: str
    agent_review_path: str
    agent_review_json: str
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


@dataclass(frozen=True)
class LongformIssue:
    severity: str
    category: str
    subject: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class LongformAuditResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    graph_path: Path
    scene_count: int
    chapter_count: int
    issue_count: int
    draft_chars: int


__all__ = ["LongformAuditResult", "LongformIssue", "LongformSceneRecord"]
