"""Readable scene-composition report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.literary.planning.narrative_rhythm import render_narrative_rhythm_contract
from .execution_contract import render_prose_execution_contract


def render_composition_report(
    root: Path,
    scene_path: Path,
    context_path: Path,
    context_trace_path: Path,
    payload: dict[str, Any],
) -> str:
    lines = [
        *_header(root, scene_path, context_path, context_trace_path, payload),
        *_branch_section(payload),
        *_beats_section(payload),
        *_characters_section(payload),
        *_dialogue_section(payload),
        *_perceptual_section(payload),
        *_contract_sections(root, scene_path, payload),
        *_expression_section(payload),
        *_closing_section(payload),
    ]
    return "\n".join(lines) + "\n"


def _header(
    root: Path,
    scene_path: Path,
    context_path: Path,
    context_trace_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    facts = payload["scene_facts"]
    return [
        f"# 场景创作编排：{payload['scene_id']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景文件：`{_relative(scene_path, root)}`",
        f"- 上下文包：`{_relative(context_path, root)}`",
        f"- 上下文 Trace：`{_relative(context_trace_path, root)}`",
        f"- 选用分支：`{payload['selected_branch'] or 'none'}`（{payload['selection_source']}）",
        f"- JSON：`drafts/compositions/{payload['scene_id']}_composition.json`",
        "",
        "## 使用边界",
        "",
        _md_list(payload["guardrails"]),
        "",
        "## 输入摘要",
        "",
        *_scene_identity_lines(facts),
        f"- 场景目标：{facts['scene_goal'] or '未填写'}",
        f"- 外部冲突：{facts['external_conflict'] or '未填写'}",
        f"- 内部冲突：{facts['internal_conflict'] or '未填写'}",
        "",
    ]


def _branch_section(payload: dict[str, Any]) -> list[str]:
    branch = payload["branch"]
    return [
        "## 选用分支",
        "",
        f"- 标题：{branch.get('title') or '未填写'}",
        f"- 策略：{branch.get('strategy') or '未填写'}",
        *_branch_identity_lines(branch),
        f"- 状态：`{branch.get('status') or 'n/a'}`",
        f"- 前提：{branch.get('premise') or '未填写'}",
        "",
        "行动链：",
        "",
        _md_list([str(item) for item in branch.get("action_chain", [])]),
        "",
    ]


def _beats_section(payload: dict[str, Any]) -> list[str]:
    lines = ["## 场景节拍", ""]
    for beat in payload["beats"]:
        lines.extend(
            [
                f"### {beat['beat_id']}：{beat['function']}",
                "",
                f"- 可见动作：{beat['visible_action']}",
                f"- 潜台词：{beat['subtext']}",
                f"- 写作提示：{beat['craft_note']}",
                "",
            ]
        )
    lines.extend(
        [render_prose_execution_contract(payload["prose_execution_contract"]).strip(), ""]
    )
    return lines


def _characters_section(payload: dict[str, Any]) -> list[str]:
    lines = ["## 人物潜台词", ""]
    for item in payload["subtext_map"]:
        lines.extend(
            [
                f"### {item['name']} `{item['character_id']}`",
                "",
                f"- 表层行动：{item['public_action']}",
                f"- 隐性压力：{item['hidden_pressure']}",
                f"- 背景影响：{item['background_influence']}",
                f"- 呈现策略：{item.get('reveal_policy', 'implicit_only')}",
                "",
                "禁止写法：",
                "",
                _md_list(item["do_not_write_directly"]),
                "",
            ]
        )
    return lines


def _dialogue_section(payload: dict[str, Any]) -> list[str]:
    lines = ["## 对白意图", ""]
    for item in payload["dialogue_intents"]:
        lines.extend(
            [
                f"- `{item['speaker']}` 想要：{item['wants']}",
                f"  避免：{item['avoids']}",
                f"  话语策略：{item['speech_strategy']}",
                f"  稳定声音：{item.get('stable_voice', {})}",
                f"  当下关系：{item.get('voice_state', {})}",
                f"  禁区：{item['forbidden_exposition']}",
            ]
        )
    return [*lines, ""]


def _perceptual_section(payload: dict[str, Any]) -> list[str]:
    sensory = payload.get("perceptual_options", {})
    return [
        "## 有依据的感知材料",
        "",
        f"- 地点锚点：{sensory.get('location_anchor') or '未指定'}",
        f"- 已登记意象：{', '.join(sensory.get('motifs', [])) or '无'}",
        "- 未列出的声音、触感和光线不应自动补入正文。",
        "",
    ]


def _contract_sections(
    root: Path,
    scene_path: Path,
    payload: dict[str, Any],
) -> list[str]:
    word = payload.get("word_budget_contract", {})
    reader = payload.get("reader_experience_contract", {})
    experience = reader.get("reader_experience", {})
    experience = experience if isinstance(experience, dict) else {}
    return [
        "## 字数预算硬属性",
        "",
        f"- 状态：`{word.get('status', 'missing')}`",
        f"- 目标中文内容字符：{word.get('target_chinese_chars') or word.get('target_words', 0)}",
        f"- 最低中文内容字符：{word.get('min_chinese_chars') or word.get('min_words', 0)}",
        f"- 最高中文内容字符：{word.get('max_chinese_chars') or word.get('max_words', 0)}",
        f"- 叙事负载：{', '.join(str(item) for item in word.get('narrative_load', [])) or '未要求'}",
        "",
        "## 读者体验硬属性",
        "",
        f"- 状态：`{reader.get('status', 'missing')}`",
        f"- 信息：{reader.get('message', '')}",
        f"- 本场读者问题：{experience.get('reader_question', '未填写')}",
        f"- 承诺回报：{experience.get('promised_reward', '未填写')}",
        f"- 兑现或延迟：{experience.get('payoff_or_delay', '未填写')}",
        f"- 反摘要要求：{experience.get('anti_summary_requirement', '未填写')}",
        "",
        "## 叙事节奏与场景桥接硬属性",
        "",
        render_narrative_rhythm_contract(root, scene_path).strip(),
        "",
    ]


def _expression_section(payload: dict[str, Any]) -> list[str]:
    plan = payload.get("expression_plan", {})
    return [
        "## 本场表达计划",
        "",
        f"- 激活轴：{', '.join(plan.get('active_axes', []))}",
        f"- 视角注意：{plan.get('focalization_lens', '')}",
        f"- 信息释放：{plan.get('information_strategy', '')}",
        f"- 句法运动：{plan.get('syntax_motion', '')}",
        f"- 对话压力：{plan.get('dialogue_pressure', '')}",
        f"- 表达渠道：{plan.get('evidence_channel', '')}",
        f"- 场尾余压：{plan.get('ending_residue', '')}",
        "",
    ]


def _closing_section(payload: dict[str, Any]) -> list[str]:
    return [
        "## 改写目标",
        "",
        _md_list(payload["revision_targets"]),
        "",
        "## 写回候选",
        "",
        _writeback_markdown(payload["writeback_candidates"]),
        "",
        "## 下一步",
        "",
        "- 按场景义务与表达计划创作正文候选。",
        "- 把候选正文放入 `drafts/scenes/` 后运行 `review-scene`。",
        "- 通过审查和人工确认后，再进入章节工作台、导出和发布链路。",
    ]


def _branch_identity_lines(branch: dict[str, Any]) -> list[str]:
    return [
        f"- 来源：`{branch.get('branch_origin') or 'missing'}`",
        f"- 固定回退理由：{branch.get('fallback_reason') or '不适用'}",
    ]


def _scene_identity_lines(facts: dict[str, Any]) -> list[str]:
    participants = ", ".join(facts["participants"]) if facts["participants"] else "未填写"
    return [
        f"- 章节：`{facts['chapter_id'] or 'n/a'}`",
        f"- 地点：{facts['location'] or '未填写'}",
        f"- 叙事视角：{facts.get('viewpoint') or '未显式配置'}",
        f"- 参与者：{participants}",
    ]


def _writeback_markdown(data: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for key, values in data.items():
        lines.append(f"- `{key}`")
        lines.extend(f"  - {value}" for value in values)
    return "\n".join(lines) if lines else "- 无。"


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = ["render_composition_report"]
