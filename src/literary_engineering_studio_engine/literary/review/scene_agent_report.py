"""Human-readable report rendering for scene review payloads."""

from __future__ import annotations


def render_scene_review_report(payload: dict[str, object], validation_status: str) -> str:
    budget = _mapping(payload, "word_budget_adherence")
    reader = _mapping(payload, "reader_experience_adherence")
    rhythm = _mapping(payload, "narrative_rhythm_adherence")
    canon = _mapping(payload, "canon_writeback")
    lines = [
        f"# Agent 场景审查：{payload.get('scene_id', '')}",
        "",
        f"- 结论：`{payload.get('conclusion', '')}`",
        f"- Schema：`{validation_status}`",
        f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
        "",
        "## 字数预算门禁",
        "",
        f"- 状态：`{budget.get('status', '')}`",
        f"- 清洗后正文中文内容字符：`{budget.get('clean_body_chinese_chars', '')}`",
        f"- 机器非空白字符诊断：`{budget.get('clean_body_machine_chars', '')}`",
        "",
        "## 读者体验门禁",
        "",
        f"- 状态：`{reader.get('status', '')}`",
        f"- 信息：{reader.get('message', '')}",
        f"- 语义复核：`{reader.get('semantic_review_required', '')}`",
        "",
        "## 叙事节奏与场景桥接门禁",
        "",
        f"- 状态：`{rhythm.get('status', '')}`",
        f"- 节奏执行：`{rhythm.get('rhythm_executed', '')}`",
        f"- 桥接执行：`{rhythm.get('bridge_executed', '')}`",
        "",
        "## Canon 写回判断",
        "",
        f"- 状态：`{canon.get('status', '')}`",
        f"- Canon 变化：`{canon.get('canon_change', '')}`",
        f"- 无变化理由：{canon.get('no_canon_change_reason', '')}",
        "",
        "## 摘要",
        "",
        str(payload.get("summary", "")),
        "",
        "## 修订动作",
        "",
    ]
    lines.extend(f"- {item}" for item in payload.get("revision_actions", []) or [])
    lines.extend(["", "## 风险", ""])
    lines.extend(f"- BLOCKING: {item}" for item in payload.get("blocking_issues", []) or [])
    lines.extend(f"- WARNING: {item}" for item in payload.get("warnings", []) or [])
    return "\n".join(lines) + "\n"


def _mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


__all__ = ["render_scene_review_report"]
