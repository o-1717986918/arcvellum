"""Complete a lean scene's planned length within its creative phase."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import json
import re
from typing import Any

from literary_engineering_studio_engine.public.literary import CreativeResult, SceneBrief
from literary_engineering_studio_engine.public.projections import count_delivery_chinese_content_chars


def complete_first_draft_length(
    brief: SceneBrief, result: CreativeResult, ask: Callable[[str], dict[str, Any]], *, actor_owned: bool = False,
    performance_material_block: str = "",
) -> CreativeResult:
    """Finish underlength prose before review, without turning length into a review gate."""
    minimum = brief.length.soft_min
    if minimum <= 0:
        return result
    initial_gap = minimum - count_delivery_chinese_content_chars(result.prose)
    max_attempts = min(24, max(8, (initial_gap + 999) // 1000 + 2))
    for _ in range(max_attempts):
        current = count_delivery_chinese_content_chars(result.prose)
        if current >= minimum:
            return result
        gap = minimum - current
        payload = ask(render_scene_length_completion_prompt(
            brief, result.prose, gap, actor_owned=actor_owned,
            performance_material_block=performance_material_block,
        ))
        insertion = str(payload.get("insertion") or "").strip()
        if not insertion or count_delivery_chinese_content_chars(insertion) < min(120, gap):
            raise ValueError("scene length completion made no meaningful progress")
        result = replace(result, prose=_insert_before_ending(result.prose, insertion))
    if count_delivery_chinese_content_chars(result.prose) < minimum:
        raise ValueError("scene creative phase did not reach its planned minimum length")
    return result


def render_scene_length_completion_prompt(
    brief: SceneBrief, prose: str, gap: int, *, actor_owned: bool = False,
    performance_material_block: str = "",
) -> str:
    """Request one insertable, causal passage without rewriting accepted prose."""
    request = min(max(gap + 120, 500), 1800)
    return "\n".join([
        "# 首轮场景正文续写",
        f"本场清洁正文距离最低篇幅尚差 {gap} 个中文内容字符。请写约 {request} 个中文内容字符的连续小说段落，插在现有正文最后一段之前。",
        "只返回 JSON 对象，字段 insertion 为新增正文字符串。",
        "寻找正文略过的一处感受、关系或空间变化，写成自然接入现有场景的段落。",
        "参考同一份一级素材，在当前视角内展开未出口的心理、情绪起伏、环境停留和叙述节奏；必要时可补写符合人物的衔接言行。若无法自然补足，返回空 insertion。" if actor_owned else "",
        "沿用已有正文的叙述距离与声音，让语言随感受变化而舒展。若最后一段是收束或悬念，新增段落自然引向它；动作、意象、对白或物证已经传意时停笔。",
        "## 本场职责\n" + json.dumps({
            "objective": brief.objective,
            "scene_function": brief.scene_function,
            "participants": brief.participants,
            "length": brief.length.target_hanzi,
        }, ensure_ascii=False, default=str),
        "## 同一份一级角色与环境素材\n" + performance_material_block if performance_material_block else "",
        "## 已有正文\n" + prose,
    ])


def _insert_before_ending(prose: str, insertion: str) -> str:
    paragraphs = prose.strip().split("\n\n")
    if len(paragraphs) == 1:
        body = prose.strip()
        endings = [match.end() for match in re.finditer(r"[。！？][”’\"]?", body)]
        if len(endings) >= 2:
            split = endings[-2]
            return body[:split].rstrip() + "\n\n" + insertion + "\n\n" + body[split:].lstrip()
        return body + "\n\n" + insertion
    return "\n\n".join([*paragraphs[:-1], insertion, paragraphs[-1]])


__all__ = ["complete_first_draft_length", "render_scene_length_completion_prompt"]
