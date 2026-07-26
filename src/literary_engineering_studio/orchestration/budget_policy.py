"""Shared numeric policy for adaptive orchestration freedom budgets."""

from __future__ import annotations

from .contracts import FreedomBudget


def budget_range_errors(budget: FreedomBudget) -> tuple[tuple[str, str], ...]:
    errors: list[tuple[str, str]] = []
    positive_fields = (
        "max_parallel_read_tasks",
        "max_branch_count",
        "max_plan_depth",
    )
    nonnegative_fields = (
        "max_added_tasks",
        "max_replans_per_scope",
        "max_research_tasks",
        "max_research_cost",
        "max_plan_stall_cycles",
    )
    for name in positive_fields:
        if getattr(budget, name) < 1:
            errors.append((name, "must be at least 1"))
    for name in nonnegative_fields:
        if getattr(budget, name) < 0:
            errors.append((name, "cannot be negative"))
    ratio = budget.max_analysis_to_production_ratio
    if ratio < 0 or ratio > 1:
        errors.append(("max_analysis_to_production_ratio", "must be between 0 and 1"))
    return tuple(errors)
