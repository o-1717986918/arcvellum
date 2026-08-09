"""Materialize the prompt, task context, execution boundaries, and ledger together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..contracts import TaskPackage, normalize_relative_path
from ..observability.context_ledger import ContextLedger
from ..protocols.review_context import validate_materialized_review_context
from .context_budget import (
    ContextBudgetExceeded,
    ContextBudgetMode,
    TaskContextBudget,
)
from .context_ledger import materialize_runtime_context_ledger
from .context_selection import AgentContextSelection
from .context_cache import (
    build_context_cache_key,
    context_cache_key_fingerprint,
)
from .execution_boundaries import materialize_execution_boundaries
from .execution_context import (
    ExecutionContextEnvelope,
    build_execution_context_envelope,
)
from .prompt_context import PreparedPromptContext, build_prepared_prompt_context
from .prepared_context_cache import PreparedContextCache
from .task_program import render_worker_program, write_task_context


@dataclass(frozen=True)
class MaterializedContextContract:
    source_paths: tuple[str, ...]
    reference_paths: tuple[str, ...]
    ledger: ContextLedger
    prepared_context: PreparedPromptContext
    execution_context: ExecutionContextEnvelope
    context_cache_status: str = "disabled"
    context_cache_key: str = ""
    context_cache_reason: str = ""


def materialize_agent_context_contract(
    task: TaskPackage,
    *,
    run_root: Path,
    run_id: str,
    workspace: Path,
    prompt_path: Path,
    task_dir: Path,
    selection: AgentContextSelection,
    copied_paths: Iterable[str],
    context_budget: TaskContextBudget | None = None,
    prepared_context_cache: PreparedContextCache | None = None,
    execution_profile: dict[str, object] | None = None,
) -> MaterializedContextContract:
    sources, references = selection.copied_prompt_paths(copied_paths)
    mandatory_paths = _mandatory_context_paths(task, context_budget)
    exact_on_demand_paths = _exact_on_demand_context_paths(task, context_budget)
    _validate_review_context(task, workspace, context_budget)
    direction = _user_direction(task)
    context_paths = (*task.core_managed_outputs, *sources, *references)
    prepared_context, cache_status, cache_key, cache_reason = _prepared_context(
        task,
        workspace,
        context_paths,
        context_budget=context_budget,
        mandatory_paths=mandatory_paths,
        exact_on_demand_paths=exact_on_demand_paths,
        cache=prepared_context_cache,
    )
    execution_context = build_execution_context_envelope(
        task,
        workspace=workspace,
        selection=selection,
        prepared_context=prepared_context,
        budget=context_budget,
        user_direction=direction,
    )
    prompt_path.write_text(
        render_worker_program(
            task,
            user_direction=direction,
            reference_paths=references,
            source_paths=sources,
            prepared_context=prepared_context.rendered,
            prepared_context_paths=prepared_context.included_paths,
            omitted_context_paths=prepared_context.omitted_paths,
            execution_context=execution_context, execution_profile=execution_profile,
        ),
        encoding="utf-8",
    )
    context_path = write_task_context(
        task,
        workspace / "TASK_CONTEXT.json",
        reference_paths=references,
        source_paths=sources,
        execution_context=execution_context, execution_profile=execution_profile,
    )
    materialize_execution_boundaries(run_root, task_dir, task_context_path=context_path)
    ledger = materialize_runtime_context_ledger(
        task,
        run_root=run_root,
        workspace=workspace,
        run_id=run_id,
        selection=selection,
        prompt_source_paths=sources,
        prompt_reference_paths=references,
        prompt_path=prompt_path,
        execution_context=execution_context,
    )
    return MaterializedContextContract(
        sources,
        references,
        ledger,
        prepared_context,
        execution_context,
        cache_status,
        cache_key,
        cache_reason,
    )


def _prepared_context(
    task: TaskPackage,
    workspace: Path,
    paths: tuple[str, ...],
    *,
    context_budget: TaskContextBudget | None,
    mandatory_paths: tuple[str, ...],
    exact_on_demand_paths: tuple[str, ...],
    cache: PreparedContextCache | None,
) -> tuple[PreparedPromptContext, str, str, str]:
    key = None
    reason = ""
    if cache is not None and cache.enabled:
        key, reason = build_context_cache_key(
            task,
            workspace,
            paths,
            budget=context_budget,
            mandatory_paths=mandatory_paths,
            exact_on_demand_paths=exact_on_demand_paths,
        )
        if key is None:
            cache.record_bypass(reason)
        else:
            cached = cache.get(key)
            if cached is not None:
                return (
                    cached,
                    "hit",
                    context_cache_key_fingerprint(key),
                    "",
                )
    prepared = build_prepared_prompt_context(
        workspace,
        paths,
        budget=context_budget,
        mandatory_paths=mandatory_paths,
        exact_on_demand_paths=exact_on_demand_paths,
    )
    if cache is None or not cache.enabled:
        return prepared, "disabled", "", "cache-disabled"
    if key is None:
        return prepared, "bypass", "", reason
    cache.put(key, prepared)
    return prepared, "miss", context_cache_key_fingerprint(key), ""


def _user_direction(task: TaskPackage) -> str:
    path = task.project_root / "workflow/studio/user_directions.md"
    if not path.is_file():
        return ""
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).strip()


def _validate_review_context(
    task: TaskPackage,
    workspace: Path,
    budget: TaskContextBudget | None,
) -> None:
    require = (
        budget is not None
        and budget.mode is ContextBudgetMode.BOUNDED
        and task.current_state == "candidate-review"
    )
    validate_materialized_review_context(
        task.payload,
        workspace,
        normalize_path=normalize_relative_path,
        require=require,
    )


def _mandatory_context_paths(
    task: TaskPackage,
    budget: TaskContextBudget | None,
) -> tuple[str, ...]:
    declared = task.payload.get("context_must_inline_paths")
    if isinstance(declared, list):
        return tuple(
            dict.fromkeys(
                str(item).replace("\\", "/")
                for item in declared
                if str(item).strip()
            )
        )
    if budget is not None and budget.mode is ContextBudgetMode.BOUNDED:
        raise ContextBudgetExceeded(
            "bounded context requires an explicit context_must_inline_paths contract"
        )
    return ()


def _exact_on_demand_context_paths(
    task: TaskPackage,
    budget: TaskContextBudget | None,
) -> tuple[str, ...]:
    if budget is None or budget.mode is not ContextBudgetMode.BOUNDED:
        return ()
    declared = task.payload.get("context_exact_on_demand_paths")
    if not isinstance(declared, list):
        return ()
    return tuple(
        dict.fromkeys(
            str(item).replace("\\", "/")
            for item in declared
            if str(item).strip()
        )
    )
