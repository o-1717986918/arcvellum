"""Materialize formal and shadow Prompt Program versions for one run."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
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

    def access_contract(
        self,
        execution_context: ExecutionContextEnvelope,
    ) -> dict[str, object]:
        """Project the final formal prompt's content-safe read contract."""
        program = self.formal.program
        if self.formal.version == "v3" and program is not None:
            inline = [item.source_ref for item in program.evidence]
            exact_on_demand = [item.source_ref for item in program.exact_on_demand]
            program_digest = program.digest
        else:
            inline = [
                *execution_context.must_inline,
                *execution_context.summary_reference_paths,
            ]
            exact_on_demand = list(execution_context.exact_on_demand)
            program_digest = ""
        payload: dict[str, object] = {
            "schema": "arcvellum/prompt-access/v1",
            "formal_version": self.formal.version,
            "renderer": self.formal.renderer,
            "program_digest": program_digest,
            "inline": list(dict.fromkeys(inline)),
            "exact_on_demand": list(dict.fromkeys(exact_on_demand)),
        }
        payload["digest"] = _contract_digest(payload)
        return payload

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
        if runtime_id == "pi-worker":
            raise ValueError(
                "Pi Worker Prompt v3 lint failed; refusing legacy v2 fallback because it can reintroduce duplicated Skill and task evidence"
            )
        if rollout.get("fallback") != "v2":
            raise ValueError("Prompt v3 lint failed and no supported fallback is configured")
        formal = v2
        rollout = {**rollout, "formal_version": "v2", "reason": "prompt-v3-lint-fallback"}
    shadow_path: Path | None = None
    if rollout["emit_shadow"] is True and v3 is not None:
        shadow_path = run_root / "prompt-v3-shadow.md"
        shadow_path.write_text(v3.text, encoding="utf-8")
    return PromptMaterialization(formal, v3 if v3 is not formal else None, shadow_path, rollout)


def _contract_digest(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = ["PromptMaterialization", "materialize_prompt_programs"]
