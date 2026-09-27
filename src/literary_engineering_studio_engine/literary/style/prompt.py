"""Validate the length and structure of mountable style prompts."""

from __future__ import annotations

import re

from literary_engineering_studio_engine.foundation.text_counts import CHINESE_CONTENT_COUNT_UNIT, count_chinese_content_chars


STYLE_PROMPT_MIN_DETAIL_CHARS = 500
STYLE_PROMPT_MAX_DETAIL_CHARS = 2500
STYLE_PROMPT_LENGTH_RULE = (
    "可靠且可挂载的 LLM 文风约束提示词必须足够详细但可执行："
    f"按中文内容字符计算为 {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} 字，"
    "计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白。"
)
STYLE_PROMPT_REQUIRED_BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("使用身份与适用边界", ("使用身份", "使用边界", "适用边界", "优先级", "适用范围")),
    ("核心风格机制", ("核心风格", "风格机制", "叙事机制", "核心约束")),
    ("叙述距离与视角", ("叙述距离", "叙述视角", "视角", "叙述者")),
    ("句法与节奏", ("句法", "节奏", "句长", "段落")),
    ("标点节奏", ("标点", "句号", "逗号", "破折号")),
    ("意象与感官调度", ("意象", "感官", "视觉", "听觉", "触觉")),
    ("心理呈现与行为因果", ("心理", "行为", "动作", "背景故事", "隐性行为因果")),
    ("对白与语气", ("对白", "语气", "话语", "说话")),
    ("AI腔控制", ("AI腔", "AI痕迹", "模型腔", "模板化", "机械对照", "不是……而是", "不是……——是")),
    ("禁止倾向", ("禁止", "避免", "不得", "不要")),
    ("输出自检", ("自检", "检查", "输出前", "评估")),
)
STYLE_PROMPT_QUALITY_RULE = (
    "高质量文风 prompt 必须具备可执行结构：身份/边界、核心风格机制、叙述距离、句法节奏、"
    "标点节奏、意象感官、心理/行为因果、对白语气、AI 腔控制、禁止倾向和输出自检。"
)


def count_style_prompt_detail_chars(text: str) -> int:
    """Count executable prompt detail as Chinese content characters."""

    total = 0
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = line.replace("`", "")
        total += count_chinese_content_chars(line)
    return total


def style_prompt_quality_report(text: str) -> dict[str, object]:
    compact = re.sub(r"\s+", "", text)
    present: list[str] = []
    missing: list[str] = []
    for label, keywords in STYLE_PROMPT_REQUIRED_BLOCKS:
        if any(keyword in compact for keyword in keywords):
            present.append(label)
        else:
            missing.append(label)
    detail_chars = count_style_prompt_detail_chars(text)
    return {
        "detail_chars": detail_chars,
        "detail_count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "count_note": "detail_chars counts Han characters and Chinese punctuation after stripping Markdown scaffolding.",
        "length_range": [STYLE_PROMPT_MIN_DETAIL_CHARS, STYLE_PROMPT_MAX_DETAIL_CHARS],
        "length_ok": STYLE_PROMPT_MIN_DETAIL_CHARS <= detail_chars <= STYLE_PROMPT_MAX_DETAIL_CHARS,
        "required_blocks": [label for label, _ in STYLE_PROMPT_REQUIRED_BLOCKS],
        "present_blocks": present,
        "missing_blocks": missing,
        "structure_ok": not missing,
    }
