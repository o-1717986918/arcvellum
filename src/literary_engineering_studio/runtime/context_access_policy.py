"""Render worker-facing rules for protected context access."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def protected_output_read_rule(
    context: Mapping[str, Any],
    *,
    prepared_paths: Iterable[str],
) -> str:
    protected = _strings(context.get("core_managed_outputs"))
    if not protected:
        return "本任务没有 CLI Protected Outputs。"

    prepared = set(prepared_paths)
    execution = context.get("execution_context")
    execution = execution if isinstance(execution, Mapping) else {}
    exact_on_demand = set(_strings(execution.get("exact_on_demand")))
    recovery = [item for item in protected if item in exact_on_demand]
    unclassified = [
        item
        for item in protected
        if item not in prepared and item not in exact_on_demand
    ]
    if unclassified:
        return (
            "下列未被 Execution Context 分类的 CLI Protected Outputs 必须逐一读取；"
            "已内联文件直接使用 Prepared Context，Exact On Demand 恢复文件只在一项"
            "具体合同信息确实缺失时读取。"
        )
    if recovery:
        return (
            "下列未内联文件已被 Execution Context 明确归类为 Exact On Demand "
            "恢复证据。当前首轮合同已经完整，禁止主动读取 `.agent_tasks.md`；"
            "正常执行只使用 Prepared Context、Semantic Evidence 和机器可读输出"
            "合同。若确定性预检失败，Studio 会在同一会话注入具体字段、错误位置和"
            "最小修复上下文，不得自行补读完整 sidecar。"
        )
    return (
        "下列 CLI Protected Outputs 的精确快照已在 Prepared Context Snapshot 中。"
        "必须逐一使用其中的 schema、字段和值，但不要再次调用读取工具。"
    )


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


__all__ = ["protected_output_read_rule"]
