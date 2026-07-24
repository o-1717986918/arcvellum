"""Compatibility facade for long-form word-budget planning.

Budget formulas, inventory scanning, formal scene contracts, and rendering live in
focused modules. Existing callers continue to import this stable entry point.
"""

from __future__ import annotations

from .literary.planning.common import (
    GENRE_PRESETS,
    WordBudgetResult,
    _now,
    _project_genre,
    _project_int,
    _read,
    _read_json,
    _rel,
    _resolve,
    _resolve_output,
    _scalar,
    _to_int,
)
from .literary.planning.contracts import (
    ensure_scene_word_budget_ready,
    load_word_budget_summary,
    scene_word_budget_contract,
    word_budget_adherence_for_body,
)
from .literary.planning.inventory import (
    _budget_issues,
    _chapter_budget_row,
    _outline_inventory,
    _scan_scene_files,
    _scene_ids_for_chapter,
    _scene_inventory_binding,
    _scene_word_count_target,
)
from .literary.planning.allocation import (
    _chapter_budgets,
    _distribute_counts,
    _distribute_words,
    _infer_volumes,
    _preset_for,
    _volume_budget,
)
from .literary.planning.rendering import (
    _render_markdown,
    _write_agent_tasks,
    _write_chapter_obligation_plan_tasks,
    _write_scene_inventory_agent_tasks,
    render_scene_word_budget_contract,
    render_word_budget_generation_standard,
)
from .literary.planning.service import build_word_budget

__all__ = [
    "GENRE_PRESETS",
    "WordBudgetResult",
    "build_word_budget",
    "ensure_scene_word_budget_ready",
    "load_word_budget_summary",
    "render_scene_word_budget_contract",
    "render_word_budget_generation_standard",
    "scene_word_budget_contract",
    "word_budget_adherence_for_body",
]
