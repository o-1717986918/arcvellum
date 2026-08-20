"""Pure Markdown rendering for character-state patch candidates."""

from __future__ import annotations

from typing import Any


def render_state_patch(payload: dict[str, Any]) -> str:
    lines = [
        f"# 人物状态演化候选 Patch：{payload['scene_id']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景：`{payload['scene']}`",
        f"- 来源产物：`{payload['source_artifact']}`",
        f"- 状态：`{payload['status']}`",
        "",
        "## 使用边界",
        "",
        _md_list(payload["guardrails"]),
        "",
        "## 候选写回",
        "",
    ]
    if not payload["characters"]:
        lines.extend(["- 未生成可匹配人物的状态 patch。", ""])
    for patch in payload["characters"]:
        lines.extend(_character_patch_lines(patch))
    lines.extend(_unresolved_lines(payload["unresolved_changes"]))
    lines.extend(
        [
            "",
            "## 人工确认清单",
            "",
            _md_list(payload["approval_required"]),
            "",
            "## 后续",
            "",
            "- 审查通过后，下一阶段才允许实现受控写回命令。",
            "- 写回前应保留本 patch 作为审批证据。",
        ]
    )
    return "\n".join(lines) + "\n"


def _character_patch_lines(patch: dict[str, Any]) -> list[str]:
    updates = patch["proposed_updates"]
    state = updates["state"]
    state_items = (
        state["known_facts_add"]
        + state["resources_add"]
        + [
            item
            for item in [state["location_note"], state["health_note"]]
            if item
        ]
    )
    return [
        f"### {patch['name']} `{patch['character_id']}`",
        "",
        f"- 人物文件：`{patch['file']}`",
        f"- 置信等级：`{patch['confidence']}`",
        "",
        "状态候选：",
        "",
        _md_list(state_items),
        "",
        "弧光候选：",
        "",
        _md_list(updates["arc"]["candidate_changes"]),
        "",
        "关系候选：",
        "",
        _md_list(updates["relationships"]["candidate_changes"]),
        "",
    ]


def _unresolved_lines(items: list[dict[str, str]]) -> list[str]:
    lines = ["## 未匹配变化", ""]
    if items:
        lines.extend(f"- `{item['kind']}`：{item['text']}" for item in items)
    else:
        lines.append("- 无。")
    return lines


def _md_list(items: list[str]) -> str:
    if not items:
        return "- 无。"
    return "\n".join(f"- {item}" for item in items)


__all__ = ["render_state_patch"]
