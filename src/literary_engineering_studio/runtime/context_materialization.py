"""Materialize the prompt, task context, execution boundaries, and ledger together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

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
from .prompt_materialization import materialize_prompt_programs
from .task_program import write_task_context


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
    prompt_program: Mapping[str, object] | None = None

    def run_manifest_fields(self, run_root: Path) -> dict[str, object]:
        return {
            "context_ledger": str(run_root / "context-ledger.json"),
            "context_ledger_id": self.ledger.ledger_id,
            "context_ledger_digest": self.ledger.digest,
            "context_assembled_sha256": self.ledger.assembled_sha256,
            "prepared_context_paths": list(self.prepared_context.included_paths),
            "omitted_context_paths": list(self.prepared_context.omitted_paths),
            "prepared_context_characters": self.prepared_context.character_count,
            "prepared_context_sha256": self.prepared_context.sha256,
            "context_budget": self.prepared_context.budget_report_dict(),
            "prepared_context_cache": {
                "status": self.context_cache_status,
                "key": self.context_cache_key,
                "reason": self.context_cache_reason,
            },
            "execution_context": self.execution_context.safe_projection(),
            "prompt_program": self.prompt_program or {},
        }


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
    cache_identity_workspace: Path | None = None,
    runtime_id: str = "host-agent",
    prompt_program_config: Mapping[str, Any] | None = None,
) -> MaterializedContextContract:
    sources, references = selection.copied_prompt_paths(copied_paths)
    mandatory_paths = _mandatory_context_paths(task, context_budget)
    exact_on_demand_paths = _exact_on_demand_context_paths(task, context_budget)
    _validate_review_context(task, workspace, context_budget)
    direction = _user_direction(task)
    prepared_context, cache_status, cache_key, cache_reason = _materialize_task_context(
        task,
        workspace,
        (*task.core_managed_outputs, *sources, *references),
        context_budget=context_budget,
        mandatory_paths=mandatory_paths,
        exact_on_demand_paths=exact_on_demand_paths,
        cache=prepared_context_cache,
        cache_identity_workspace=cache_identity_workspace,
    )
    execution_context = build_execution_context_envelope(
        task,
        workspace=workspace,
        selection=selection,
        prepared_context=prepared_context,
        budget=context_budget,
        user_direction=direction,
    )
    prompt_program = _materialize_prompt(
        task, workspace, run_root, runtime_id, prompt_program_config, direction,
        references, sources, prepared_context, execution_context, execution_profile,
    )
    prompt_path.write_text(prompt_program.formal.text, encoding="utf-8")
    prompt_access = prompt_program.access_contract(execution_context)
    context_path = write_task_context(
        task,
        workspace / "TASK_CONTEXT.json",
        reference_paths=references,
        source_paths=sources,
        execution_context=execution_context,
        execution_profile=execution_profile,
        prompt_access=prompt_access,
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
        prompt_program.safe_projection(run_root),
    )


def _materialize_prompt(
    task: TaskPackage,
    workspace: Path,
    run_root: Path,
    runtime_id: str,
    config: Mapping[str, Any] | None,
    direction: str,
    references: tuple[str, ...],
    sources: tuple[str, ...],
    prepared: PreparedPromptContext,
    execution_context: ExecutionContextEnvelope,
    execution_profile: dict[str, object] | None,
):
    return materialize_prompt_programs(
        task,
        workspace=workspace,
        run_root=run_root,
        runtime_id=runtime_id,
        config=config,
        user_direction=direction,
        reference_paths=references,
        source_paths=sources,
        prepared_context=prepared.rendered,
        prepared_context_paths=prepared.included_paths,
        omitted_context_paths=prepared.omitted_paths,
        execution_context=execution_context,
        execution_profile=execution_profile,
    )


def _materialize_task_context(
    task: TaskPackage,
    workspace: Path,
    paths: tuple[str, ...],
    *,
    context_budget: TaskContextBudget | None,
    mandatory_paths: tuple[str, ...],
    exact_on_demand_paths: tuple[str, ...],
    cache: PreparedContextCache | None,
    cache_identity_workspace: Path | None,
) -> tuple[PreparedPromptContext, str, str, str]:
    active_cache = cache if cache is not None and cache.allows(task.route, task.current_state) else None
    result = _prepared_context(
        task,
        workspace,
        paths,
        context_budget=context_budget,
        mandatory_paths=mandatory_paths,
        exact_on_demand_paths=exact_on_demand_paths,
        cache=active_cache,
        cache_identity_workspace=cache_identity_workspace,
    )
    if cache is not None and cache.enabled and active_cache is None:
        prepared, status, key, _ = result
        return prepared, status, key, "cache-task-outside-allowlist"
    return result


def _prepared_context(
    task: TaskPackage,
    workspace: Path,
    paths: tuple[str, ...],
    *,
    context_budget: TaskContextBudget | None,
    mandatory_paths: tuple[str, ...],
    exact_on_demand_paths: tuple[str, ...],
    cache: PreparedContextCache | None,
    cache_identity_workspace: Path | None,
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
            trace_workspace=cache_identity_workspace,
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
    # Visibility is part of the task contract, not a bounded-budget feature.
    # Rollout mode controls the inline limit and blocking behavior only.
    del budget
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
