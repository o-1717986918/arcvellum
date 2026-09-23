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
        payload = ask(render_scene_length_completion_prompt(brief, result.prose, gap, actor_owned=actor_owned))
        insertion = str(payload.get("insertion") or "").strip()
        if not insertion or count_delivery_chinese_content_chars(insertion) < min(120, gap):
            raise ValueError("scene length completion made no meaningful progress")
        result = replace(result, prose=_insert_before_ending(result.prose, insertion))
    if count_delivery_chinese_content_chars(result.prose) < minimum:
        raise ValueError("scene creative phase did not reach its planned minimum length")
    return result


def render_scene_length_completion_prompt(brief: SceneBrief, prose: str, gap: int, *, actor_owned: bool = False) -> str:
    """Request one insertable, causal passage without rewriting accepted prose."""
    request = min(max(gap + 120, 500), 1800)
    return "\n".join([
        "# 首轮场景正文续写",
        f"本场清洁正文距离最低篇幅尚差 {gap} 个中文内容字符。请写约 {request} 个中文内容字符的连续小说段落，插在现有正文最后一段之前。",
        "只返回 JSON 对象，字段 insertion 为新增正文字符串。不要重写或重复原文，不写提纲、自评、解释或元叙述。",
        "沿现有场景已经发生的行动链深化阻力、核验、人物反应与选择代价；不要添加新人物、新稳定世界事实或新核心事件，不提前完成后续场景职责，也不要靠计件描写灌字数。",
        "本场人物言行由一级角色 Agent 先生成；此轮不能新增或改写任何人物对白、手势、操作及其他可见行为。只在已有动作之间补充不引入新事实的感知、叙述节奏与内在迟疑。若无法自然补足，返回空 insertion，不得伪造角色表演。" if actor_owned else "",
        "先从已有正文辨认叙述距离、句群呼吸、主导意象和人物话语策略，再用同一语言谱面续写；白描不能独占补写段，承压处可沿用已有的自由间接感知、反讽、借代、通感、复沓、意象回返或长句推进，但不凭空加华丽辞藻。",
        "若最后一段是收束或悬念，新增段落必须自然引向它；动作、意象、对白或物证已经传意时停笔，不追加翻译潜台词、概括感受或解释意义的尾句。保持人物话语差异与已挂载文风。",
        "## 本场职责\n" + json.dumps({
            "objective": brief.objective,
            "scene_function": brief.scene_function,
            "participants": brief.participants,
            "length": brief.length.target_hanzi,
        }, ensure_ascii=False, default=str),
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
