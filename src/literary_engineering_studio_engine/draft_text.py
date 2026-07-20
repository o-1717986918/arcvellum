"""Shared helpers for final-delivery draft body extraction and counting."""

from __future__ import annotations

import re
from pathlib import Path

from .text_counts import chinese_machine_count_mapping, count_chinese_content_chars, count_nonspace_chars

INTERNAL_HEADING_RE = re.compile(
    r"(?im)^\s{0,3}#{1,6}\s*(状态变化|状态变化候选|世界状态变化|角色状态变化|场景状态变化|世界线变化|"
    r"写回|写回清单|写回候选|写回候选汇总|状态写回|自检|创作说明|工作流程|"
    r"审查|审查状态|canon|Canon|上下文|提示词|Prompt|需要人工确认|新增事实候选|人物状态变化|关系变化|伏笔变化|"
    r"新角色|新角色候选|新角色候选登记)\b.*$"
)
PROSE_SECTION_RE = re.compile(r"(?ms)^##\s*(正文草稿|正文候选|修订正文候选)\s*\n(.*?)(?=^##\s+|\Z)")
INTERNAL_SCENE_ID_RE = re.compile(r"\bscene[_-]?\d{1,6}\b", re.IGNORECASE)
INTERNAL_SCENE_LINE_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:[-*]\s*)?"
    r"(?:(?:scene|scene_id|场景编号|场景文件|上下文包)\s*[:：]?\s*)?"
    r"scene[_-]?\d{1,6}(?:\s*[:：\-|].*)?\s*$",
    re.IGNORECASE,
)
INTERNAL_SCENE_META_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:[-*]\s*)?"
    r"(?:scene_id|场景编号|场景文件|上下文包|draft_path|context_packet)\s*[:：]",
    re.IGNORECASE,
)
INTERNAL_STATE_META_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:[-*]\s*)?"
    r"(?:状态变化|状态变化候选|世界状态变化|角色状态变化|场景状态变化|世界线变化|"
    r"新增事实候选|人物状态变化|关系变化|伏笔变化|新角色候选|新角色候选登记|写回候选|需要人工确认)\s*[:：]",
    re.IGNORECASE,
)


def final_body_from_draft_text(text: str) -> str:
    """Return the body that is allowed to count as deliverable prose."""

    return final_body_from_workbench_text(text).strip()


def final_body_from_workbench_text(text: str) -> str:
    """Extract prose from a draft/candidate/revision workbench artifact."""

    match = PROSE_SECTION_RE.search(text)
    if match:
        return clean_final_body(match.group(2)).strip()
    return clean_final_body(text).strip()


def final_body_from_draft_path(path: Path) -> str:
    if not path.exists():
        return ""
    return final_body_from_draft_text(path.read_text(encoding="utf-8", errors="ignore"))


def clean_final_body(text: str) -> str:
    """Remove workbench-only traces from prose before final export or stats."""

    body = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    match = INTERNAL_HEADING_RE.search(body)
    if match:
        body = body[: match.start()].strip()
    cleaned_lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if INTERNAL_SCENE_LINE_RE.search(line) or INTERNAL_SCENE_META_RE.search(line) or INTERNAL_STATE_META_RE.search(line):
            continue
        if re.search(
            r"(canon|Canon|workflow|prompt manifest|AGENT_TASK|上下文包|写回候选|新增事实候选|人物状态变化|"
            r"世界状态变化|角色状态变化|场景状态变化|世界线变化|新角色候选|新角色候选登记|需要人工确认)",
            line,
        ):
            continue
        cleaned_line = INTERNAL_SCENE_ID_RE.sub("", raw_line.rstrip())
        cleaned_line = re.sub(r"[ \t]{2,}", " ", cleaned_line).strip()
        if cleaned_line and not re.fullmatch(r"#{1,6}|[-*：:|]+", cleaned_line):
            cleaned_lines.append(cleaned_line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()


def count_delivery_chars(text: str) -> int:
    """Count cleaned deliverable body characters without whitespace."""

    return count_nonspace_chars(final_body_from_workbench_text(text))


def count_delivery_chinese_content_chars(text: str) -> int:
    """Count cleaned Chinese deliverable body characters, including Chinese punctuation."""

    return count_chinese_content_chars(final_body_from_workbench_text(text))


def delivery_char_count_mapping(text: str, *, target_chinese_chars: int = 0) -> dict[str, object]:
    """Map cleaned Chinese body counts to the machine non-whitespace diagnostic count."""

    return chinese_machine_count_mapping(final_body_from_workbench_text(text), target_chinese_chars=target_chinese_chars)
