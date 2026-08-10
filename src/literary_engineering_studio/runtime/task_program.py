"""Compile a host-neutral task package into the concise Studio Worker program."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ..contracts import TaskPackage
from .context_selection import compact_task_references
from .context_access_policy import protected_output_read_rule
from .creative_plan_context import creative_plan_task_context
from .execution_context import (
    ExecutionContextEnvelope,
    execution_context_program_fields,
)
from .prompt_context import PreparedPromptContext, render_prepared_context_section
from .prompt_compiler import compile_prompt_program
from .prompt_metrics import PromptLintReport, PromptMetrics, lint_prompt, measure_prompt
from .prompt_program import PromptProgram
from .prompt_recipes import prompt_recipe
from .prompt_renderer import render_file_agent_program, render_tool_worker_program
from .task_completion import (
    build_task_completion_contract,
    completion_program_fields,
)
from .task_semantic_contract import (
    render_semantic_output_contract,
    semantic_output_contract,
)
from .worker_program_template import WORKER_PROGRAM_TEMPLATE


_EMPTY_PROMPT_ACCESS: Mapping[str, object] = MappingProxyType({})


@dataclass(frozen=True)
class CompiledWorkerProgram:
    text: str
    version: str
    renderer: str
    metrics: PromptMetrics
    lint: PromptLintReport | None
    program: PromptProgram | None

    def safe_projection(self) -> dict[str, object]:
        return {
            "version": self.version,
            "renderer": self.renderer,
            "metrics": self.metrics.safe_projection(),
            "lint": self.lint.safe_projection() if self.lint is not None else {},
            "program": self.program.safe_projection() if self.program is not None else {},
        }

def build_task_context(
    task: TaskPackage,
    *,
    reference_paths: tuple[str, ...] | None = None,
    source_paths: tuple[str, ...] | None = None,
    execution_context: ExecutionContextEnvelope | None = None,
    execution_profile: dict[str, Any] | None = None,
    prompt_access: Mapping[str, object] = _EMPTY_PROMPT_ACCESS,
) -> dict[str, Any]:
    prompt_asset = task.payload.get("prompt_asset") if isinstance(task.payload.get("prompt_asset"), dict) else {}
    agent_sources = task.payload.get("agent_source_paths")
    default_sources = _strings(agent_sources) if isinstance(agent_sources, list) else list(task.source_paths)
    output_contracts = [item.as_dict() for item in task.execution_contract.outputs]
    semantic_output = semantic_output_contract(task)
    return {
        "schema": "literary-engineering-studio/task-context/v0.2",
        "compatible_with": ["literary-engineering-studio/task-context/v0.1"],
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "scene_id": str(task.payload.get("scene_id") or ""),
        "agent_role": task.execution_contract.agent_role,
        "execution_policy": task.execution_contract.execution_policy,
        "writeback_policy": task.execution_contract.writeback_policy,
        "source_paths": list(source_paths) if source_paths is not None else default_sources,
        "workspace_dependency_paths": list(task.source_paths),
        "reference_paths": list(reference_paths if reference_paths is not None else compact_task_references(task)),
        "expected_outputs": list(task.expected_outputs),
        "core_managed_outputs": list(task.core_managed_outputs),
        "output_contracts": output_contracts,
        "semantic_artifact": task.semantic_artifact,
        "semantic_output_contract": semantic_output,
        "system_owned_fields": _system_owned_fields(task),
        "completion_contract": build_task_completion_contract(
            task,
            output_contracts=output_contracts,
            semantic_output_contract=semantic_output,
        ),
        "execution_profile": _profile_projection(execution_profile),
        "creative_plan": creative_plan_task_context(task.payload),
        "command": task.command,
        "word_count": {
            "target": int(task.payload.get("word_count_target") or 0),
            "minimum": int(task.payload.get("word_count_min") or 0),
            "maximum": int(task.payload.get("word_count_max") or 0),
        },
        "hard_constraints": _strings(task.payload.get("hard_constraints")),
        "style_constraints": _strings(task.payload.get("style_constraints")),
        "validation_gates": _strings(task.payload.get("validation_gates")),
        "forbidden_shortcuts": [
            item
            for item in _strings(task.payload.get("forbidden_shortcuts"))
            if "task-submit" not in item and "task-complete" not in item
        ],
        "prompt_asset": {
            key: prompt_asset.get(key)
            for key in (
                "resolved_id",
                "version",
                "title",
                "body",
                "required_inputs",
                "optional_inputs",
                "context_groups",
                "hard_constraints",
                "style_constraints",
                "output_contract",
                "review_requirements",
                "forbidden_shortcuts",
            )
        },
        "execution_context": (
            execution_context.as_dict()
            if execution_context is not None
            else {}
        ),
        "prompt_access": dict(prompt_access),
    }


def write_task_context(
    task: TaskPackage,
    path: Path,
    *,
    reference_paths: tuple[str, ...] | None = None,
    source_paths: tuple[str, ...] | None = None,
    execution_context: ExecutionContextEnvelope | None = None,
    execution_profile: dict[str, Any] | None = None,
    prompt_access: Mapping[str, object] = _EMPTY_PROMPT_ACCESS,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_task_context(
                task,
                reference_paths=reference_paths,
                source_paths=source_paths,
                execution_context=execution_context,
                execution_profile=execution_profile,
                prompt_access=prompt_access,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def render_worker_program(
    task: TaskPackage, *, user_direction: str = "",
    reference_paths: tuple[str, ...] | None = None, source_paths: tuple[str, ...] | None = None,
    prepared_context: str = "",
    prepared_context_paths: tuple[str, ...] = (),
    omitted_context_paths: tuple[str, ...] = (),
    execution_context: ExecutionContextEnvelope | None = None,
    execution_profile: dict[str, Any] | None = None,
    prompt_version: str = "v2",
    renderer: str = "file-agent",
    workspace: Path | None = None,
    prompt_lint_config: Mapping[str, Any] | None = None,
) -> str:
    return compile_worker_program(
        task,
        user_direction=user_direction,
        reference_paths=reference_paths,
        source_paths=source_paths,
        prepared_context=prepared_context,
        prepared_context_paths=prepared_context_paths,
        omitted_context_paths=omitted_context_paths,
        execution_context=execution_context,
        execution_profile=execution_profile,
        prompt_version=prompt_version,
        renderer=renderer,
        workspace=workspace,
        prompt_lint_config=prompt_lint_config,
    ).text


def compile_worker_program(
    task: TaskPackage,
    *,
    user_direction: str = "",
    reference_paths: tuple[str, ...] | None = None,
    source_paths: tuple[str, ...] | None = None,
    prepared_context: str = "",
    prepared_context_paths: tuple[str, ...] = (),
    omitted_context_paths: tuple[str, ...] = (),
    execution_context: ExecutionContextEnvelope | None = None,
    execution_profile: dict[str, Any] | None = None,
    prompt_version: str = "v2",
    renderer: str = "file-agent",
    workspace: Path | None = None,
    prompt_lint_config: Mapping[str, Any] | None = None,
) -> CompiledWorkerProgram:
    context = build_task_context(
        task,
        reference_paths=reference_paths,
        source_paths=source_paths,
        execution_context=execution_context,
        execution_profile=execution_profile,
    )
    if prompt_version == "v3":
        if execution_context is None or workspace is None:
            raise ValueError("Prompt v3 requires workspace and execution context")
        program = compile_prompt_program(
            task,
            workspace=workspace,
            task_context=context,
            execution_context=execution_context,
            user_direction=user_direction,
        )
        if renderer == "tool-worker":
            text = render_tool_worker_program(program)
        elif renderer == "file-agent":
            text = render_file_agent_program(program)
        else:
            raise ValueError(f"unsupported Prompt v3 renderer: {renderer}")
        metrics = measure_prompt(text)
        recipe = prompt_recipe(execution_context.task_kind)
        outputs = program.output_contract.get("outputs")
        output_count = len(outputs) if isinstance(outputs, list) else 0
        lint = lint_prompt(
            metrics,
            hard_character_limit=recipe.hard_character_limit,
            output_count=output_count,
            duplicate_warning_ratio=_float_setting(
                prompt_lint_config, "duplicate_warning_ratio", 0.15
            ),
            duplicate_error_ratio=_float_setting(
                prompt_lint_config, "duplicate_error_ratio", 0.25
            ),
        )
        return CompiledWorkerProgram(text, "v3", renderer, metrics, lint, program)
    if prompt_version != "v2":
        raise ValueError(f"unsupported Prompt version: {prompt_version}")
    prepared = PreparedPromptContext(
        rendered=prepared_context,
        included_paths=prepared_context_paths,
        omitted_paths=omitted_context_paths,
        character_count=len(prepared_context),
        sha256="",
    )
    fields = _worker_program_fields(task, context, user_direction, prepared)
    text = WORKER_PROGRAM_TEMPLATE.format_map(fields)
    return CompiledWorkerProgram(text, "v2", "file-agent", measure_prompt(text), None, None)


def _worker_program_fields(
    task: TaskPackage,
    context: dict[str, Any],
    user_direction: str,
    prepared: PreparedPromptContext,
) -> dict[str, Any]:
    asset = context["prompt_asset"]
    fields = {
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "agent_role": task.execution_contract.agent_role,
        "direction": user_direction.strip() or "没有额外的用户方向；只执行当前任务合同。",
        "task_body": asset.get("body") or "按当前任务合同完成声明的产物。",
    }
    fields.update(_output_program_fields(context))
    fields.update(_constraint_program_fields(context, asset))
    fields.update(_semantic_program_fields(context, fields["output_contracts"]))
    fields.update(
        completion_program_fields(
            context.get("completion_contract") or {},
            execution_context=context.get("execution_context") or {},
            fallback_sources=(*context["source_paths"], *context["reference_paths"]),
        )
    )
    fields.update(_prepared_program_fields(context, prepared))
    fields.update(
        execution_context_program_fields(
            (
                context.get("execution_context")
                if isinstance(context.get("execution_context"), dict)
                else {}
            ),
            prepared,
            fallback_paths=(
                *context["source_paths"],
                *context["reference_paths"],
            ),
        )
    )
    fields.pop("output_contracts")
    return fields


def _output_program_fields(context: dict[str, Any]) -> dict[str, Any]:
    output_contracts = {
        str(item.get("path") or ""): item
        for item in context["output_contracts"]
        if isinstance(item, dict)
    }
    protected = set(context["core_managed_outputs"])
    agent_outputs = [
        item
        for item in context["expected_outputs"]
        if item not in protected and str(output_contracts.get(item, {}).get("kind") or "") != "completion-evidence"
    ]
    return {
        "output_contracts": output_contracts,
        "output_lines": _path_lines(agent_outputs, empty="- 无 Agent 创作文件输出"),
        "protected_lines": _path_lines(context["core_managed_outputs"]),
    }


def _constraint_program_fields(context: dict[str, Any], asset: dict[str, Any]) -> dict[str, str]:
    return {
        "constraints": _bullet_block(
            [
                *context["hard_constraints"],
                *_strings(asset.get("hard_constraints")),
                *_strings(asset.get("style_constraints")),
            ]
        ),
        "gates": _bullet_block(context["validation_gates"]),
        "output_contract": _bullet_block(_strings(asset.get("output_contract"))),
        "review": _bullet_block(_strings(asset.get("review_requirements"))),
        "shortcuts": _bullet_block(
            [
                *context["forbidden_shortcuts"],
                *[
                    item
                    for item in _strings(asset.get("forbidden_shortcuts"))
                    if "task-submit" not in item and "task-complete" not in item
                ],
            ]
        ),
    }


def _semantic_program_fields(
    context: dict[str, Any],
    output_contracts: dict[str, dict[str, Any]],
) -> dict[str, str]:
    semantic = context.get("semantic_artifact") if isinstance(context.get("semantic_artifact"), dict) else {}
    semantic_contract = context.get("semantic_output_contract") if isinstance(context.get("semantic_output_contract"), dict) else {}
    semantic_line = (
        f"- 语义成果：`{semantic.get('path')}`，schema=`{semantic.get('schema_name')}`，后续消费者=`{semantic.get('consumed_by')}`"
        if semantic
        else "- 语义成果：本任务无单独语义成果契约。"
    )
    receipt_paths = [
        item
        for item in context["expected_outputs"]
        if str(output_contracts.get(item, {}).get("kind") or "") == "completion-evidence"
    ]
    receipt_notice = (
        "Studio 会在语义成果通过预检后自动写入执行回执：" + "、".join(f"`{item}`" for item in receipt_paths) + "。"
        "不要自行创建、修改或以回执替代语义判断。"
        if receipt_paths
        else "本任务没有由 Studio 托管的执行回执。"
    )
    return {
        "semantic_line": semantic_line,
        "semantic_rules": render_semantic_output_contract(semantic_contract),
        "receipt_notice": receipt_notice,
    }


def _prepared_program_fields(
    context: dict[str, Any],
    prepared: PreparedPromptContext,
) -> dict[str, str]:
    return {
        "prepared_section": render_prepared_context_section(prepared),
        "protected_read_rule": protected_output_read_rule(
            context,
            prepared_paths=prepared.included_paths,
        ),
    }


def _path_lines(paths: list[str] | tuple[str, ...], *, empty: str = "- 无") -> str:
    return "\n".join(f"- `{item}`" for item in paths) or empty


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()] if isinstance(value, list) else []


def _bullet_block(values: list[str]) -> str:
    unique: list[str] = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return "\n".join(f"- {item}" for item in unique) or "- 无额外约束"


def _profile_projection(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value else {}


def _system_owned_fields(task: TaskPackage) -> dict[str, Any]:
    value = task.payload.get("system_owned_fields")
    return dict(value) if isinstance(value, dict) else {}


def _float_setting(
    config: Mapping[str, Any] | None,
    key: str,
    default: float,
) -> float:
    try:
        return float((config or {}).get(key, default))
    except (TypeError, ValueError):
        return default
