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
    audience: str = "file-agent",
) -> PromptProgram:
    recipe = prompt_recipe(execution_context.task_kind)
    asset = _mapping(task_context.get("prompt_asset"))
    evidence = compile_evidence(
        task,
        workspace,
        execution_context,
        audience=audience,
    )
    objective = _objective(
        user_direction,
        str(asset.get("body") or ""),
        audience=audience,
    )
    decisions = _decisions(asset, recipe, audience=audience)
    constraints = _constraints(
        task_context,
        asset,
        task_kind=execution_context.task_kind,
        audience=audience,
    )
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


def _objective(
    user_direction: str,
    task_body: str,
    *,
    audience: str = "file-agent",
) -> str:
    parts = []
    if user_direction.strip():
        parts.append("用户方向：\n" + _audience_text(user_direction.strip(), audience))
    parts.append(
        _audience_text(task_body.strip(), audience)
        or "按当前任务合同完成声明的产物。"
    )
    return "\n\n".join(parts)


def _decisions(
    asset: Mapping[str, Any],
    recipe: PromptRecipe,
    *,
    audience: str,
) -> tuple[str, ...]:
    # Review/promotion obligations belong to Studio's later Gates, not to the
    # current Pi prose turn. Host-skill Agents retain the explanatory list.
    if audience == "tool-worker" and recipe.task_kind.value == "prose":
        return ()
    values: list[str] = []
    for field in recipe.decision_sources:
        values.extend(_strings(asset.get(field)))
    return _unique(_audience_text(value, audience) for value in values)


def _constraints(
    context: Mapping[str, Any],
    asset: Mapping[str, Any],
    *,
    task_kind: str,
    audience: str = "file-agent",
) -> tuple[str, ...]:
    execution_protocol: tuple[str, ...] = ()
    if task_kind == "prose":
        word_count = _mapping(context.get("word_count"))
        target = int(word_count.get("target") or 0)
        minimum = int(word_count.get("minimum") or 0)
        maximum = int(word_count.get("maximum") or 0)
        budget_rule = (
            f"本任务只写当前场景，清洁正文目标为 {target} 个中文内容字符，"
            f"可接受范围 {minimum}-{maximum}；作品总字数只决定全书分配，不得在本场一次写完。"
            if target and minimum and maximum
            else "本任务只写当前场景；作品总字数只决定全书分配，不得在本场一次写完。"
        )
        execution_protocol = (
            "正文任务只完成正文及其直接 manifest；人物、世界、状态等资产由独立任务处理，不得在正文回合扩张职责。",
            budget_rule,
            "候选 manifest 只填写语义契约列出的模型负责字段；schema、路径、摘要、运行身份与会话 provenance 由 Studio 自动补齐。",
        )
    values = [
        *execution_protocol,
        *_strings(context.get("hard_constraints")),
        *_strings(context.get("style_constraints")),
        *_strings(asset.get("hard_constraints")),
        *_strings(asset.get("style_constraints")),
    ]
    if audience != "tool-worker":
        values.extend(_strings(context.get("validation_gates")))
        values.extend(_strings(context.get("forbidden_shortcuts")))
    values.extend(_strings(asset.get("forbidden_shortcuts")))
    return _unique(
        _audience_text(value, audience)
        for value in values
        if not _runtime_owned_constraint(value, audience)
    )


def _runtime_owned_constraint(value: str, audience: str) -> bool:
    if audience != "tool-worker":
        return False
    lowered = " ".join(value.casefold().split())
    fragments = (
        "task-submit",
        "task-complete",
        "route audit",
        "route-audit",
        "skill-host",
        "--allow-",
        "debug approval bypass",
        "debug/bypass",
        "studio has already run",
        "do not run cli",
        "do not skip prompt manifest",
        "sidecar completed",
        "sidecar is complete",
        "read the generated prompt manifest and sidecar",
    )
    return any(fragment in lowered for fragment in fragments)


def _audience_text(value: str, audience: str) -> str:
    if audience != "tool-worker":
        return value
    replacements = (
        ("main platform Agent", "current main Worker"),
        ("main platform agent", "current main Worker"),
        ("platform Agent", "Worker"),
        ("platform agent", "Worker"),
        ("CLI task package", "task contract"),
        ("The CLI", "Studio"),
        ("the CLI", "Studio"),
        ("CLI-created", "Studio-created"),
        ("CLI-generated", "Studio-generated"),
        ("CLI-managed", "Studio-managed"),
        ("CLI-owned", "Studio-owned"),
        ("CLI handoff", "structured handoff"),
        ("CLI lifecycle", "Studio lifecycle"),
        ("CLI ", "Studio "),
        ("sidecar", "task contract"),
        ("mounted Style Skill", "mounted style profile"),
        ("mounted style skill", "mounted style profile"),
    )
    normalized = value
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return normalized


def _output_contract(context: Mapping[str, Any]) -> dict[str, object]:
    protected = set(_strings(context.get("core_managed_outputs")))
    outputs = []
    for value in context.get("output_contracts") or []:
        if not isinstance(value, Mapping):
            continue
        path = str(value.get("path") or "")
        if not path or path in protected or value.get("kind") == "completion-evidence":
            continue
        suffix = Path(path).suffix.casefold()
        inferred_format = {
            ".json": "json",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
        }.get(suffix, "text")
        outputs.append(
            {
                "path": path,
                "kind": str(value.get("kind") or "agent-authored"),
                "format": str(value.get("format") or inferred_format),
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
            "object_shapes",
            "model_owned_fields",
            "studio_owned_fields",
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
