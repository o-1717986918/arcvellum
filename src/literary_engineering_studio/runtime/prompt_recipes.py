"""Table-driven Prompt v3 recipes by canonical task kind."""

from __future__ import annotations

from dataclasses import dataclass

from .context_budget import ContextTaskKind


@dataclass(frozen=True)
class PromptRecipe:
    recipe_id: str
    task_kind: ContextTaskKind
    soft_character_limit: int
    hard_character_limit: int
    max_on_demand_reads: int
    decision_sources: tuple[str, ...]


_RECIPES = {
    ContextTaskKind.STRUCTURED: PromptRecipe(
        "prompt-v3/structured/v1", ContextTaskKind.STRUCTURED, 12_000, 18_000, 1,
        ("output_contract", "review_requirements"),
    ),
    ContextTaskKind.CREATIVE: PromptRecipe(
        "prompt-v3/creative/v1", ContextTaskKind.CREATIVE, 42_000, 60_000, 2,
        ("review_requirements", "output_contract"),
    ),
    ContextTaskKind.PLANNING: PromptRecipe(
        "prompt-v3/planning/v1", ContextTaskKind.PLANNING, 32_000, 48_000, 2,
        ("output_contract", "review_requirements"),
    ),
    ContextTaskKind.STYLE: PromptRecipe(
        "prompt-v3/style/v1", ContextTaskKind.STYLE, 40_000, 55_000, 2,
        ("review_requirements", "output_contract"),
    ),
    ContextTaskKind.ARCHAEOLOGY: PromptRecipe(
        "prompt-v3/archaeology/v1", ContextTaskKind.ARCHAEOLOGY, 36_000, 50_000, 2,
        ("output_contract", "review_requirements"),
    ),
    ContextTaskKind.PROSE: PromptRecipe(
        "prompt-v3/prose/v2", ContextTaskKind.PROSE, 65_000, 90_000, 2,
        ("style_constraints", "output_contract", "review_requirements"),
    ),
    ContextTaskKind.REVIEW: PromptRecipe(
        "prompt-v3/review/v1", ContextTaskKind.REVIEW, 36_000, 48_000, 2,
        (),
    ),
}


def prompt_recipe(task_kind: str | ContextTaskKind) -> PromptRecipe:
    kind = task_kind if isinstance(task_kind, ContextTaskKind) else ContextTaskKind(task_kind)
    return _RECIPES[kind]


__all__ = ["PromptRecipe", "prompt_recipe"]
