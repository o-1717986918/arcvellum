"""Validate the scene creator's decision before any candidate is generated."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


_AVAILABILITY_REASON = re.compile(
    r"(?:素材(?:库|目录|文件)?|候选|material|candidate|index|目录).{0,14}"
    r"(?:为空|是空|空目录|没有|无候选|缺少|empty|none|unavailable|not available)"
    r"|(?:空|没有|无|缺少|empty|none).{0,14}"
    r"(?:素材(?:库|目录|文件)?|候选|material|candidate|index)",
    re.IGNORECASE,
)


class MaterialSelectionError(ValueError):
    """A focused material selection correction was exhausted."""


def initial_material_choice_error(payload: dict[str, Any]) -> str:
    """Return a repairable error; the absence of preexisting files is not a literary choice."""
    requests = payload.get("material_requests")
    if requests:
        if not isinstance(requests, list):
            return "material_requests must be a list"
        if str(payload.get("prose") or "").strip():
            return "material_requests must be answered before writing prose"
        return ""
    reason = str(payload.get("material_skip_reason") or "").strip()
    if not 10 <= len(reason) <= 300:
        return "initial direct scene draft needs a specific literary material_skip_reason"
    if _AVAILABILITY_REASON.search(reason):
        return "material_skip_reason cannot use the empty candidate library as a reason"
    return ""


def material_selection_error(
    payload: dict[str, Any], candidate_ids: list[str], prior_decisions: list[dict[str, str]],
) -> str:
    """Require at least one accountable choice when the creator finishes with candidates."""
    if not candidate_ids or payload.get("material_requests"):
        return ""
    if payload.get('material_selection_pending'):
        return str(payload['material_selection_pending'])
    decisions = payload.get("material_decisions")
    if not isinstance(decisions, list):
        return "material_decisions must list a real candidate choice"
    known = set(candidate_ids)
    for item in decisions:
        if not isinstance(item, dict):
            return "material_decisions must contain candidate records"
        identifier = str(item.get("candidate_id") or "").strip()
        if identifier not in known:
            return f"material_decisions must refer to known candidate IDs; unknown candidate_id: {identifier!r}"
        if item.get("decision") not in {"use", "adapt", "discard", "defer"}:
            return f"material_decisions must use valid choices (use/adapt/discard/defer); {identifier!r} has decision {item.get('decision')!r}"
        if not str(item.get("reason") or "").strip():
            return "material_decisions need a literary reason"
    if not decisions and not prior_decisions:
        return "material_decisions must list a real candidate choice"
    return ""


def repair_material_choice(
    payload: dict[str, Any], prompt: str, *, phase: str,
    candidate_ids: list[str], prior_decisions: list[dict[str, str]],
    invoke: Callable[[str], dict[str, Any]],
    natural: bool = False,
) -> tuple[dict[str, Any], str]:
    """Give each invalid creator choice one bounded chance to correct itself."""
    if phase == "opening":
        issue = initial_material_choice_error(payload)
        if issue:
            prompt += "\n\n" + prompt_layer_spec("scene.creator.material-choice-repair.protocol").default_text
            payload = invoke(prompt)
            issue = initial_material_choice_error(payload)
        if issue:
            raise ValueError(issue)
    issue = material_selection_error(payload, candidate_ids, prior_decisions)
    if issue:
        guidance = _selection_repair_guidance(payload, candidate_ids, issue, natural)
        prompt = guidance if natural else prompt + "\n\n" + guidance
        corrected = invoke(prompt)
        payload = {**payload, "material_decisions": corrected.get("material_decisions")}
        payload.pop('material_selection_pending', None)
        if corrected.get('source_provenance'):
            payload['material_selection_provenance'] = corrected['source_provenance']
        issue = material_selection_error(payload, candidate_ids, prior_decisions)
        if issue:
            raise MaterialSelectionError(issue)
    return payload, prompt


def _selection_repair_guidance(payload, candidate_ids, issue, natural):
    output = ("请以自然语言补交取舍记录，仅补待核对的部分：写出 candidate_id、use/adapt/discard/defer 和文学理由。"
              "保留已经说明的选中来源原句、当前正文落点或间接用途，不为补编号而丢掉这些依据。"
              "未判断的材料不必强行采用或舍下；留待后文使用 defer 并说明去处。"
              if natural else '请返回 {"material_decisions":[{"candidate_id":"候选清单中的 ID","decision":"use/adapt/discard/defer","reason":"文学理由"}]}。')
    return "\n".join((
        prompt_layer_spec("scene.creator.material-selection-repair.protocol").default_text,
        "校验发现：" + issue,
        "已提供的候选 ID：" + json.dumps(candidate_ids, ensure_ascii=False),
        "上一份取舍：" + json.dumps(payload.get("material_decisions"), ensure_ascii=False),
        "整理时待核对的编号线索：" + json.dumps(payload.get('unverified_material_decisions', []), ensure_ascii=False),
        "本轮正文与 SceneDelta 已经记录，这次交付用于补齐素材取舍。",
        "已记录的正文：\n" + str(payload.get("prose") or ""), output,
    ))


__all__ = ["MaterialSelectionError", "initial_material_choice_error", "material_selection_error", "repair_material_choice"]
