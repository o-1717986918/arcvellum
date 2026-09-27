"""Render worker-facing rules for protected context access."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from literary_engineering_studio_engine.public.prompting import render_prompt_template


def protected_output_read_rule(
    context: Mapping[str, Any],
    *,
    prepared_paths: Iterable[str],
) -> str:
    protected = _strings(context.get("core_managed_outputs"))
    if not protected:
        return render_prompt_template("formal.context-access.none.protocol", ()).strip()

    prepared = set(prepared_paths)
    execution = context.get("execution_context")
    execution = execution if isinstance(execution, Mapping) else {}
    exact_on_demand = set(_strings(execution.get("exact_on_demand")))
    recovery = [item for item in protected if item in exact_on_demand]
    unclassified = [
        item
        for item in protected
        if item not in prepared and item not in exact_on_demand
    ]
    if unclassified:
        return render_prompt_template("formal.context-access.unclassified.protocol", ()).strip()
    if recovery:
        return render_prompt_template("formal.context-access.recovery.protocol", ()).strip()
    return render_prompt_template("formal.context-access.prepared.protocol", ()).strip()


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


__all__ = ["protected_output_read_rule"]
