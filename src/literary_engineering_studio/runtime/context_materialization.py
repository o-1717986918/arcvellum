"""Materialize the prompt, task context, execution boundaries, and ledger together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..contracts import TaskPackage
from ..observability.context_ledger import ContextLedger
from .context_ledger import materialize_runtime_context_ledger
from .context_selection import AgentContextSelection
from .execution_boundaries import materialize_execution_boundaries
from .prompt_context import PreparedPromptContext, build_prepared_prompt_context
from .task_program import render_worker_program, write_task_context


@dataclass(frozen=True)
class MaterializedContextContract:
    source_paths: tuple[str, ...]
    reference_paths: tuple[str, ...]
    ledger: ContextLedger
    prepared_context: PreparedPromptContext


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
) -> MaterializedContextContract:
    sources, references = selection.copied_prompt_paths(copied_paths)
    direction_path = task.project_root / "workflow/studio/user_directions.md"
    direction = (
        direction_path.read_text(encoding="utf-8", errors="ignore").strip()
        if direction_path.is_file()
        else ""
    )
    prepared_context = build_prepared_prompt_context(
        workspace,
        (
            *task.core_managed_outputs,
            *sources,
            *references,
        ),
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
        ),
        encoding="utf-8",
    )
    context_path = write_task_context(
        task,
        workspace / "TASK_CONTEXT.json",
        reference_paths=references,
        source_paths=sources,
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
    )
    return MaterializedContextContract(sources, references, ledger, prepared_context)
