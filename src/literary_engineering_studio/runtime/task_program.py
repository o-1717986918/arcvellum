"""Compile a host-neutral task package into the concise Studio Worker program."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from literary_engineering_studio_engine.agent_schema import load_schema_spec
from .context_selection import compact_task_references
from .context_access_policy import protected_output_read_rule
from .creative_plan_context import creative_plan_task_context
from .execution_context import (
    ExecutionContextEnvelope,
    execution_context_program_fields,
)
from .prompt_context import PreparedPromptContext, render_prepared_context_section
from .worker_program_template import WORKER_PROGRAM_TEMPLATE

def build_task_context(
    task: TaskPackage,
    *,
    reference_paths: tuple[str, ...] | None = None,
    source_paths: tuple[str, ...] | None = None,
    execution_context: ExecutionContextEnvelope | None = None,
) -> dict[str, Any]:
    prompt_asset = task.payload.get("prompt_asset") if isinstance(task.payload.get("prompt_asset"), dict) else {}
    agent_sources = task.payload.get("agent_source_paths")
    default_sources = _strings(agent_sources) if isinstance(agent_sources, list) else list(task.source_paths)
    return {
        "schema": "literary-engineering-studio/task-context/v0.1",
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
        "output_contracts": [item.as_dict() for item in task.execution_contract.outputs],
        "semantic_artifact": task.semantic_artifact,
        "semantic_output_contract": _semantic_output_contract(task),
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
    }


def write_task_context(
    task: TaskPackage,
    path: Path,
    *,
    reference_paths: tuple[str, ...] | None = None,
    source_paths: tuple[str, ...] | None = None,
    execution_context: ExecutionContextEnvelope | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_task_context(
                task,
                reference_paths=reference_paths,
                source_paths=source_paths,
                execution_context=execution_context,
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
) -> str:
    context = build_task_context(
        task,
        reference_paths=reference_paths,
        source_paths=source_paths,
        execution_context=execution_context,
    )
    prepared = PreparedPromptContext(
        rendered=prepared_context,
        included_paths=prepared_context_paths,
        omitted_paths=omitted_context_paths,
        character_count=len(prepared_context),
        sha256="",
    )
    fields = _worker_program_fields(task, context, user_direction, prepared)
    return WORKER_PROGRAM_TEMPLATE.format_map(fields)


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
        "semantic_rules": _render_semantic_output_contract(semantic_contract),
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


def _semantic_output_contract(task: TaskPackage) -> dict[str, Any]:
    """Project the exact semantic JSON contract into the sandbox task package.

    The initial semantic file is deliberately a pending scaffold.  Showing only
    its schema name left lightweight worker models unable to distinguish a
    valid review from that scaffold, especially during repair turns.
    """

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    continuity = _continuity_ledger_output_contract(current_state, scene_id)
    if continuity:
        return continuity

    semantic = task.semantic_artifact
    schema_name = str(semantic.get("schema_name") or "").strip()
    if not schema_name:
        return {}
    try:
        schema = load_schema_spec(schema_name)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        return {"path": str(semantic.get("path") or ""), "schema_name": schema_name}

    template: dict[str, Any] = {}
    path = task.project_root / str(semantic.get("path") or "")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        template = parsed if isinstance(parsed, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass

    locked = {
        field: template[field]
        for field in ("schema", "scene_id", "source_artifact", "composition_sha256", "state_patch_sha256", "canon_patch_sha256")
        if field in template and template[field] not in {"", None}
    }
    contract: dict[str, Any] = {
        "path": str(semantic.get("path") or ""),
        "schema_name": schema_name,
        "required_fields": list(schema.get("required") or []),
        "field_types": dict(schema.get("types") or {}),
        "allowed_values": dict(schema.get("enums") or {}),
        "locked_values": locked,
        "current_state": current_state,
    }
    if current_state == "composition-agent-task":
        scene_id = str(task.payload.get("scene_id") or "")
        composition = f"drafts/compositions/{scene_id}_composition.json"
        contract["pass_requirements"] = {
            "status": "complete",
            "verdict": "pass",
            "ready_for_generation": True,
            "required_changes": [],
            "evidence_paths": [composition, f"drafts/compositions/{scene_id}_composition.md"],
            "findings": "A non-empty list of concrete checked conditions; record positive validation when no defect remains.",
        }
        contract["revision_requirements"] = {
            "status": "needs_revision",
            "verdict": "revise_required",
            "ready_for_generation": False,
            "required_changes": "A non-empty list of concrete changes required before a new review.",
        }
    elif current_state in {"state-agent-task", "canon-agent-task"}:
        source_label = "state patch" if current_state == "state-agent-task" else "Canon patch"
        contract["pass_requirements"] = {
            "status": "complete",
            "verdict": "pass",
            "approval_recommendation": "approve",
            "required_changes": [],
            "evidence_paths": [str(locked.get("source_artifact") or "")],
            "findings": (
                f"A non-empty list of concrete evidence-backed checks showing why the {source_label} "
                "is safe to send to its separate approval boundary."
            ),
        }
        contract["revision_requirements"] = {
            "status": "needs_revision",
            "verdict": "revise_required",
            "approval_recommendation": "hold",
            "required_changes": "A non-empty list of concrete changes required before a new review.",
        }
    return contract


def _continuity_ledger_output_contract(current_state: str, scene_id: str) -> dict[str, Any]:
    """Expose the ledger contract as a first-class Agent output brief."""

    if not scene_id:
        return {}
    if current_state == "continuity-ledger-agent-task":
        return {
            "path": f"plot/ledger_deltas/{scene_id}.json",
            "schema_name": "continuity-ledger-delta/v1",
            "required_fields": [
                "schema", "status", "scene_id", "source_draft", "source_draft_sha256",
                "writer_session_id", "evidence_paths", "reader_question_changes", "promise_changes", "no_change_reason",
            ],
            "field_types": {
                "evidence_paths": "list",
                "reader_question_changes": "list",
                "promise_changes": "list",
                "no_change_reason": "str",
            },
            "allowed_values": {"status": ["complete"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                "scene_id": scene_id,
                "source_draft": f"drafts/scenes/{scene_id}.md",
            },
            "continuity_kind": "delta",
        }
    if current_state == "continuity-ledger-review":
        return {
            "path": f"reviews/continuity/{scene_id}_ledger_review.json",
            "schema_name": "continuity-ledger-review/v1",
            "required_fields": [
                "schema", "status", "scene_id", "delta_path", "delta_sha256", "writer_session_id",
                "reviewer_session_id", "verdict", "findings", "required_changes",
            ],
            "field_types": {"findings": "list", "required_changes": "list"},
            "allowed_values": {"status": ["complete"], "verdict": ["pass"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-review/v1",
                "scene_id": scene_id,
                "delta_path": f"plot/ledger_deltas/{scene_id}.json",
            },
            "continuity_kind": "review",
        }
    return {}


def _render_semantic_output_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return "若声明语义成果，先完成真实判断；不得把 pending 模板或 completion receipt 当作正式结论。"

    path = str(contract.get("path") or "")
    required = ", ".join(f"`{item}`" for item in contract.get("required_fields") or []) or "无"
    allowed = contract.get("allowed_values") if isinstance(contract.get("allowed_values"), dict) else {}
    allowed_lines = "\n".join(
        f"- `{field}` 只能取：" + "、".join(f"`{value}`" for value in values)
        for field, values in allowed.items()
        if isinstance(values, list)
    ) or "- 无枚举字段"
    locked = contract.get("locked_values") if isinstance(contract.get("locked_values"), dict) else {}
    locked_lines = "\n".join(f"- `{field}`：`{value}`" for field, value in locked.items()) or "- 无预填机器值"
    base = f"""该 JSON 当前是故意设置的 pending 初始模板，不能原样保留。必须使用 edit 工具完成 `{path}`，而不是只在聊天中说明审查结果。

必填字段：{required}

允许值：
{allowed_lines}

以下机器值必须保留，不得自行改写：
{locked_lines}"""
    continuity_kind = str(contract.get("continuity_kind") or "")
    if continuity_kind == "delta":
        return base + """

这不是可选记录，初始化的 `pending_agent_judgment` 不能原样提交。完成判断后必须设为 `status=complete`。

- 存在新建、更新、延期、兑现、反转或关闭的读者问题/承诺时：两个 changes 列表按实际填写，每条都必须来自已晋升正文，并在 `evidence_paths` 中引用正文路径。
- 确实没有任何账本变化时：两个 changes 列表保持空数组，并写出具体的 `no_change_reason`，说明正文为什么没有产生新的读者责任。
- `source_draft_sha256` 与 `writer_session_id` 由 Studio 绑定到本次任务；不要编造或以 completion receipt 代替正文判断。
- 只编辑 delta，不要编辑 `plot/reader_questions/ledger.json` 或 `plot/promises/ledger.json`。
"""
    if continuity_kind == "review":
        return base + """

这是一份独立复核，不是对模板的确认。核对 delta 的每一项是否有已晋升正文证据、是否重复旧问题、是否给出了合理的未来兑现窗口。

- 审查通过时：`status=complete`、`verdict=pass`、`findings` 非空、`required_changes=[]`。
- 发现问题时：不能伪造 pass；写出可执行的 `required_changes`，等待原作者重新提交 delta。
- `writer_session_id`、`reviewer_session_id` 和 delta 摘要由 Studio 绑定；不要自行创建 completion receipt，也不要编辑正式账本。
"""
    pass_requirements = contract.get("pass_requirements") if isinstance(contract.get("pass_requirements"), dict) else {}
    revision_requirements = contract.get("revision_requirements") if isinstance(contract.get("revision_requirements"), dict) else {}
    if not pass_requirements:
        return base
    pass_lines = [
        f"- `status`: `{pass_requirements['status']}`",
        f"- `verdict`: `{pass_requirements['verdict']}`",
    ]
    if "ready_for_generation" in pass_requirements:
        pass_lines.append(f"- `ready_for_generation`: `true`")
    if "approval_recommendation" in pass_requirements:
        pass_lines.append(f"- `approval_recommendation`: `{pass_requirements['approval_recommendation']}`")
    evidence_paths = pass_requirements.get("evidence_paths") or []
    if evidence_paths and evidence_paths[0]:
        pass_lines.append(f"- `evidence_paths`: 至少保留可读的证据路径，例如 `{evidence_paths[0]}`")
    pass_lines.extend(
        [
            f"- `findings`: {pass_requirements['findings']}",
            "- `required_changes`: `[]`",
        ]
    )
    revision_lines = [
        f"`status={revision_requirements.get('status')}`",
        f"`verdict={revision_requirements.get('verdict')}`",
    ]
    if "ready_for_generation" in revision_requirements:
        revision_lines.append("`ready_for_generation=false`")
    if "approval_recommendation" in revision_requirements:
        revision_lines.append(f"`approval_recommendation={revision_requirements['approval_recommendation']}`")
    return base + f"""

若审查确认可进入下一步，必须同时写入：
{chr(10).join(pass_lines)}

若确有实质问题，不得伪造 pass；使用 {'、'.join(revision_lines)}，并写出可执行的 `required_changes`。"""
