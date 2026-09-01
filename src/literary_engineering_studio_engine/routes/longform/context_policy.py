"""Agent-visible context policy for longform planning tasks."""

from __future__ import annotations

from ...task_paths import normalize_relative_path


_AGENT_SOURCES = {
    "story-architecture-agent-task": (
        "project.yaml",
        "plot/outline.md",
        "plot/story_architecture.candidate.json",
    ),
    "story-architecture-review": (
        "project.yaml",
        "plot/story_architecture.candidate.json",
        "reviews/longform/story_architecture_review.json",
    ),
    "story-architecture-revision": (
        "project.yaml",
        "plot/outline.md",
        "plot/story_architecture.candidate.json",
        "reviews/longform/story_architecture_review.json",
    ),
    "budget-agent-task": (
        "project.yaml",
        "plot/outline.md",
        "plot/word_budget/word_budget.json",
    ),
    "scene-inventory-agent-task": (
        "plot/word_budget/word_budget.json",
        "plot/candidates/outlines/word_budget_expansion.md",
    ),
    "chapter-obligation-agent-task": (
        "project.yaml",
        "plot/outline.md",
        "plot/word_budget/word_budget.json",
        "plot/candidates/scenes/word_budget_scene_inventory.md",
    ),
    "chapter-obligation-review": (
        "plot/word_budget/word_budget.json",
        "plot/candidates/chapters/chapter_obligation_plan.md",
        "reviews/word_budget/chapter_obligation_review.md",
    ),
}


def apply_agent_context_policy(
    state: str,
    blueprint: dict[str, object],
) -> dict[str, object]:
    sources = _AGENT_SOURCES.get(state)
    if sources is None:
        return blueprint
    projected = dict(blueprint)
    projected["required_reading"] = []
    projected["agent_source_paths"] = list(sources)
    return projected


def agent_context_payload(blueprint: dict[str, object]) -> dict[str, object]:
    sources = blueprint.get("agent_source_paths")
    if not isinstance(sources, list):
        return {}
    return {
        "agent_source_paths": list(
            dict.fromkeys(normalize_relative_path(item) for item in sources)
        )
    }
