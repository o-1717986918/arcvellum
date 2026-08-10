"""Materialize formal and shadow Prompt Program versions for one run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..contracts import TaskPackage
from .execution_context import ExecutionContextEnvelope
from .prompt_program import resolve_prompt_program_rollout
from .task_program import CompiledWorkerProgram, compile_worker_program


@dataclass(frozen=True)
class PromptMaterialization:
    formal: CompiledWorkerProgram
    shadow: CompiledWorkerProgram | None
    shadow_path: Path | None
    rollout: Mapping[str, object]

    def safe_projection(self, run_root: Path) -> dict[str, object]:
        return {
            "schema": "arcvellum/prompt-materialization/v1",
            "rollout": dict(self.rollout),
            "formal": self.formal.safe_projection(),
            "shadow": self.shadow.safe_projection() if self.shadow is not None else {},
            "shadow_path": (
                self.shadow_path.relative_to(run_root).as_posix()
                if self.shadow_path is not None
                else ""
            ),
        }


def materialize_prompt_programs(
    task: TaskPackage,
    *,
    workspace: Path,
    run_root: Path,
    runtime_id: str,
    config: Mapping[str, Any] | None,
    user_direction: str,
    reference_paths: tuple[str, ...],
    source_paths: tuple[str, ...],
    prepared_context: str,
    prepared_context_paths: tuple[str, ...],
    omitted_context_paths: tuple[str, ...],
    execution_context: ExecutionContextEnvelope,
    execution_profile: dict[str, object] | None,
) -> PromptMaterialization:
    common = {
        "user_direction": user_direction,
        "reference_paths": reference_paths,
        "source_paths": source_paths,
        "prepared_context": prepared_context,
        "prepared_context_paths": prepared_context_paths,
        "omitted_context_paths": omitted_context_paths,
        "execution_context": execution_context,
        "execution_profile": execution_profile,
        "workspace": workspace,
        "prompt_lint_config": (
            config.get("lint") if isinstance(config, Mapping) else {}
        ),
    }
    v2 = compile_worker_program(task, prompt_version="v2", **common)
    rollout = resolve_prompt_program_rollout(
        config,
        runtime_id=runtime_id,
        task_kind=execution_context.task_kind,
        route=task.route,
        current_state=task.current_state,
    )
    needs_v3 = rollout["formal_version"] == "v3" or rollout["emit_shadow"] is True
    v3 = (
        compile_worker_program(
            task,
            prompt_version="v3",
            renderer="tool-worker" if runtime_id == "pi-worker" else "file-agent",
            **common,
        )
        if needs_v3
        else None
    )
    formal = v3 if rollout["formal_version"] == "v3" and v3 is not None else v2
    if formal is v3 and v3 is not None and v3.lint is not None and v3.lint.status == "error":
        if rollout.get("fallback") != "v2":
            raise ValueError("Prompt v3 lint failed and no supported fallback is configured")
        formal = v2
        rollout = {**rollout, "formal_version": "v2", "reason": "prompt-v3-lint-fallback"}
    shadow_path: Path | None = None
    if rollout["emit_shadow"] is True and v3 is not None:
        shadow_path = run_root / "prompt-v3-shadow.md"
        shadow_path.write_text(v3.text, encoding="utf-8")
    return PromptMaterialization(formal, v3 if v3 is not formal else None, shadow_path, rollout)


__all__ = ["PromptMaterialization", "materialize_prompt_programs"]
