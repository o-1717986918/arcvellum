"""Deterministic completion projection for one Agent-owned task."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from ..contracts import TaskPackage


COMPLETION_CONTRACT_SCHEMA = "arcvellum/task-completion-contract/v1"


def build_task_completion_contract(
    task: TaskPackage,
    *,
    output_contracts: Sequence[Mapping[str, Any]],
    semantic_output_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Project existing task facts into one Agent-facing completion contract."""

    by_path = {
        str(item.get("path") or ""): item
        for item in output_contracts
        if str(item.get("path") or "")
    }
    protected = set(task.core_managed_outputs)
    agent_outputs: list[dict[str, str]] = []
    studio_evidence: list[str] = []
    for relative in task.expected_outputs:
        contract = by_path.get(relative, {})
        kind = str(contract.get("kind") or "agent-authored")
        if kind == "completion-evidence":
            studio_evidence.append(relative)
            continue
        if relative in protected:
            continue
        agent_outputs.append(
            {
                "path": relative,
                "kind": kind,
                "format": _output_format(relative),
                "schema_name": str(contract.get("schema_name") or ""),
                "required_state": "exists_nonempty_and_preflight_valid",
            }
        )

    review_requirement = _review_conclusion_requirement(task)
    pass_checks = [
        "all_agent_owned_outputs_exist_and_are_nonempty",
        "all_declared_machine_formats_are_valid",
        "no_undeclared_workspace_changes",
        "studio_deterministic_preflight_passes",
    ]
    if semantic_output_contract:
        pass_checks.append("semantic_artifact_satisfies_exact_contract")
    if review_requirement == "pass":
        pass_checks.append("review_machine_conclusion_is_pass")
    elif review_requirement == "recorded":
        pass_checks.append("review_machine_conclusion_is_recorded")
    if int(task.payload.get("word_count_min") or 0) > 0:
        pass_checks.append("declared_word_count_minimum_is_satisfied")

    return {
        "schema": COMPLETION_CONTRACT_SCHEMA,
        "agent_owned_outputs": agent_outputs,
        "studio_managed_completion_evidence": studio_evidence,
        "semantic_pass_condition": {
            "authoritative_validator": "studio-deterministic-preflight",
            "required_checks": pass_checks,
            "review_conclusion": review_requirement,
            "semantic_artifact": dict(semantic_output_contract),
        },
        "stop_condition": {
            "status": "return_control",
            "when": "all_agent_owned_outputs_written_and_self_checked",
            "chat_is_not_an_output": True,
            "do_not_create_completion_evidence": True,
        },
    }


def completion_program_fields(
    contract: Mapping[str, Any],
    *,
    execution_context: Mapping[str, Any] | None = None,
    fallback_sources: Sequence[str] = (),
) -> dict[str, str]:
    outputs = contract.get("agent_owned_outputs")
    output_rows = outputs if isinstance(outputs, list) else []
    checklist = "\n".join(
        _output_line(index, item)
        for index, item in enumerate(output_rows, start=1)
        if isinstance(item, Mapping)
    ) or "- 本任务没有 Agent 创作文件输出。"

    pass_condition = contract.get("semantic_pass_condition")
    semantic = pass_condition if isinstance(pass_condition, Mapping) else {}
    checks = semantic.get("required_checks")
    check_rows = checks if isinstance(checks, list) else []
    pass_lines = "\n".join(f"- `{item}`" for item in check_rows) or "- Studio 确定性预检通过。"
    review_requirement = str(semantic.get("review_conclusion") or "")
    if review_requirement == "pass":
        pass_lines += "\n- 审查 Markdown 必须包含独占机器行：`- 结论： pass`。标题、代码字段或普通段落不能替代。"
    elif review_requirement == "recorded":
        pass_lines += (
            "\n- 审查 Markdown 必须包含独占机器行：`- 结论： pass`、"
            "`- 结论： revise_required` 或 `- 结论： reject`。标题、代码字段或普通段落不能替代。"
        )

    stop = contract.get("stop_condition")
    stop_payload = stop if isinstance(stop, Mapping) else {}
    stop_lines = "\n".join(
        (
            "- 所有 Agent-owned 文件写完并逐项自检后，立即把控制权交还 Studio。",
            "- 不用聊天文本宣告完成；聊天内容不计入产物。",
            "- 不创建或修改 Studio 托管的 completion evidence。",
        )
    )
    if not bool(stop_payload.get("do_not_create_completion_evidence", True)):
        stop_lines = stop_lines.rsplit("\n", 1)[0]
    return {
        "required_reading_lines": _reading_lines(
            execution_context or {}, fallback_sources
        ),
        "completion_checklist": checklist,
        "semantic_pass_conditions": pass_lines,
        "stop_conditions": stop_lines,
    }


def _reading_lines(
    envelope: Mapping[str, Any], fallback_sources: Sequence[str]
) -> str:
    must_inline = envelope.get("must_inline")
    required = must_inline if isinstance(must_inline, list) else list(fallback_sources)
    exact = envelope.get("exact_on_demand")
    on_demand = exact if isinstance(exact, list) else []
    return "\n".join(
        [
            *(f"- 首轮必须使用：`{item}`" for item in required),
            *(f"- 仅在一条具体判断缺证据时按需读取：`{item}`" for item in on_demand),
        ]
    ) or "- 本任务没有额外项目资料；只使用任务包内联合同。"


def _output_line(index: int, item: Mapping[str, Any]) -> str:
    path = str(item.get("path") or "")
    kind = str(item.get("kind") or "agent-authored")
    output_format = str(item.get("format") or "file")
    schema_name = str(item.get("schema_name") or "")
    schema_note = f"，schema=`{schema_name}`" if schema_name else ""
    return f"{index}. `{path}`：{kind}，{output_format}{schema_note}；必须存在、非空并通过预检。"


def _review_conclusion_requirement(task: TaskPackage) -> str:
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if "conclusion is pass" in gates:
        return "pass"
    if "conclusion is recorded" in gates or "结论" in gates:
        return "recorded"
    return "not_required"


def _output_format(relative: str) -> str:
    suffix = PurePosixPath(relative).suffix.lower()
    return {
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "file")


__all__ = [
    "COMPLETION_CONTRACT_SCHEMA",
    "build_task_completion_contract",
    "completion_program_fields",
]
