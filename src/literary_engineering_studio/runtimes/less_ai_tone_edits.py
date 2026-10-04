"""Apply source-local literary edits while keeping observable facts and evidence."""
from __future__ import annotations
import re
from typing import Any, Sequence

_QUOTES = re.compile(r'“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|"[^"\n]*"', re.S)
_NUMBERS = re.compile(r"\d+(?:\.\d+)?[%％]?|[零〇一二三四五六七八九十百千万亿两]+(?:年|月|日|天|次|岁|米|小时|分钟|秒|个|人)")
_CODE = re.compile(r"```[\s\S]*?```")
_STRUCTURE = re.compile(r"^(?:#{1,6}\s|>\s?|[-*+]\s|\d+[.)]\s|\|)", re.M)


def apply_tone_edits(prose: str, edits: Any, protected: Sequence[str] = ()):
    if not isinstance(edits, list) or len(edits) > 32:
        raise ValueError("tone extraction needs at most 32 local edits")
    accepted, rejected, ranges = [], [], []
    for edit in edits:
        issue, span = _edit_issue(prose, edit, ranges, protected)
        if issue:
            rejected.append({"edit": edit, "reason": issue})
            continue
        accepted.append({key: edit[key] for key in ("rule_id", "before", "after", "reason")})
        ranges.append(span)
    cleaned = prose
    for edit, (start, end) in sorted(zip(accepted, ranges), key=lambda pair: pair[1][0], reverse=True):
        cleaned = cleaned[:start] + edit["after"] + cleaned[end:]
    issue = _preservation_issue(prose, cleaned, protected)
    if issue:
        rejected.extend({"edit": edit, "reason": issue} for edit in accepted)
        return prose, [], rejected
    return cleaned, accepted, rejected


def _edit_issue(prose, edit, ranges, protected):
    if not isinstance(edit, dict):
        return "局部建议格式无效", None
    if str(edit.get("rule_id")) not in {str(value) for value in range(1, 12)}:
        return "规则编号没有对应十一项参考规则", None
    before, after = edit.get("before"), edit.get("after")
    if not isinstance(before, str) or not before.strip() or not isinstance(after, str):
        return "原片段或替换片段无效", None
    if not str(edit.get("reason") or "").strip() or before == after:
        return "建议缺少文学理由或文字保持相同", None
    if prose.count(before) != 1:
        return "原片段需要在正文中唯一定位", None
    start, end = prose.index(before), prose.index(before) + len(before)
    if any(start < right and left < end for left, right in ranges):
        return "建议与已采用的片段重叠", None
    candidate = prose[:start] + after + prose[end:]
    return _preservation_issue(prose, candidate, protected), (start, end)


def _preservation_issue(before, after, protected):
    for expression, label in ((_QUOTES, "引文与角色对白"), (_NUMBERS, "数字与时点"), (_CODE, "代码原文")):
        if expression.findall(before) != expression.findall(after):
            return label + "发生变化，保留原稿"
    if before.count("\n") != after.count("\n") or re.findall(r"\n\s*\n", before) != re.findall(r"\n\s*\n", after):
        return "段落结构发生变化，保留原稿"
    if _STRUCTURE.findall(before) != _STRUCTURE.findall(after):
        return "标题、列表或引文结构发生变化，保留原稿"
    if any(text and before.count(text) != after.count(text) for text in protected):
        return "人物名或场景交接证据发生变化，保留原稿"
    return ""
