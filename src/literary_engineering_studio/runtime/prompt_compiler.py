"""Compile one formal task and execution context into Prompt Program v3."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ..contracts import TaskPackage
from .evidence_compiler import compile_evidence
from .execution_context import ExecutionContextEnvelope
from .prompt_program import (
    PROMPT_PROGRAM_SCHEMA,
    PromptProgram,
    prompt_program_digest,
)
from .prompt_recipes import PromptRecipe, prompt_recipe


def compile_prompt_program(
    task: TaskPackage,
    *,
    workspace: Path,
    task_context: Mapping[str, Any],
    execution_context: ExecutionContextEnvelope,
    user_direction: str,
) -> PromptProgram:
    recipe = prompt_recipe(execution_context.task_kind)
    asset = _mapping(task_context.get("prompt_asset"))
    evidence = compile_evidence(task, workspace, execution_context)
    objective = _objective(user_direction, str(asset.get("body") or ""))
    decisions = _decisions(asset, recipe)
    constraints = _constraints(task_context, asset)
    output_contract = _output_contract(task_context)
    stop_contract = (
        "写完所有 Agent-owned outputs 并逐项检查格式与内容。",
        "不要创建或修改 Studio 管理的 completion evidence。",
        "不要用聊天文本、分析或计划替代正式产物。",
        "没有可验证进展或证据冲突无法解决时停止并报告阻断。",
    )
    identity = {
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "agent_role": task.execution_contract.agent_role,
        "task_kind": execution_context.task_kind,
        "execution_context_digest": execution_context.context_digest,
    }
    digest = prompt_program_digest(
        recipe_id=recipe.recipe_id,
        task_identity=identity,
        objective=objective,
        decisions=decisions,
        constraints=constraints,
        output_contract=output_contract,
        evidence=evidence.inline,
        exact_on_demand=evidence.exact_on_demand,
        stop_contract=stop_contract,
    )
    return PromptProgram(
        schema=PROMPT_PROGRAM_SCHEMA,
        recipe_id=recipe.recipe_id,
        task_identity=identity,
        objective=objective,
        decisions=decisions,
        constraints=constraints,
        output_contract=output_contract,
        evidence=evidence.inline,
        exact_on_demand=evidence.exact_on_demand,
        stop_contract=stop_contract,
        compile_metrics={
            **evidence.safe_metrics(),
            "soft_character_limit": recipe.soft_character_limit,
            "hard_character_limit": recipe.hard_character_limit,
            "max_on_demand_reads": recipe.max_on_demand_reads,
        },
        digest=digest,
    )


def _objective(user_direction: str, task_body: str) -> str:
    parts = []
    if user_direction.strip():
        parts.append("用户方向：\n" + user_direction.strip())
    parts.append(task_body.strip() or "按当前任务合同完成声明的产物。")
    return "\n\n".join(parts)


def _decisions(asset: Mapping[str, Any], recipe: PromptRecipe) -> tuple[str, ...]:
    values: list[str] = []
    for field in recipe.decision_sources:
        values.extend(_strings(asset.get(field)))
    return _unique(values)


def _constraints(
    context: Mapping[str, Any],
    asset: Mapping[str, Any],
) -> tuple[str, ...]:
    return _unique(
        (
            *_strings(context.get("hard_constraints")),
            *_strings(context.get("style_constraints")),
            *_strings(asset.get("hard_constraints")),
            *_strings(asset.get("style_constraints")),
            *_strings(context.get("validation_gates")),
            *_strings(context.get("forbidden_shortcuts")),
            *_strings(asset.get("forbidden_shortcuts")),
        )
    )


def _output_contract(context: Mapping[str, Any]) -> dict[str, object]:
    protected = set(_strings(context.get("core_managed_outputs")))
    outputs = []
    for value in context.get("output_contracts") or []:
        if not isinstance(value, Mapping):
            continue
        path = str(value.get("path") or "")
        if not path or path in protected or value.get("kind") == "completion-evidence":
            continue
        outputs.append(
            {
                "path": path,
                "kind": str(value.get("kind") or "agent-authored"),
                "format": str(value.get("format") or "text"),
                "required": value.get("required") is not False,
            }
        )
    semantic = _mapping(context.get("semantic_output_contract"))
    compact_semantic = {
        key: semantic[key]
        for key in (
            "path",
            "schema_name",
            "required_fields",
            "field_types",
            "allowed_values",
            "locked_values",
            "pass_requirements",
            "revision_requirements",
            "continuity_kind",
            "branch_proposal_contract",
        )
        if key in semantic
    }
    machine_contract = _mapping(context.get("system_owned_fields"))
    agent_visible_machine_contract = {
        key: machine_contract[key]
        for key in ("candidate", "review", "enums")
        if key in machine_contract
    }
    return {
        "outputs": outputs,
        "semantic": compact_semantic,
        "machine_contract": agent_visible_machine_contract,
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.split()).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return tuple(result)


__all__ = ["compile_prompt_program"]
