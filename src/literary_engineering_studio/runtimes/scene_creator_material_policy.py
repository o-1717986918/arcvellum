"""Validate the scene creator's decision before any candidate is generated."""

from __future__ import annotations

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
    decisions = payload.get("material_decisions")
    if not isinstance(decisions, list):
        return "material_decisions must list a real candidate choice"
    known = set(candidate_ids)
    for item in decisions:
        if not isinstance(item, dict):
            return "material_decisions must contain candidate records"
        identifier = str(item.get("candidate_id") or "").strip()
        if identifier not in known or item.get("decision") not in {"use", "adapt", "discard"}:
            return "material_decisions must refer to known candidate IDs and valid choices"
        if not str(item.get("reason") or "").strip():
            return "material_decisions need a literary reason"
    if not decisions and not prior_decisions:
        return "material_decisions must list a real candidate choice"
    return ""


def repair_material_choice(
    payload: dict[str, Any], prompt: str, *, phase: str,
    candidate_ids: list[str], prior_decisions: list[dict[str, str]],
    invoke: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Give each invalid creator choice one bounded chance to correct itself."""
    checks = (
        (phase == "opening", initial_material_choice_error, "scene.creator.material-choice-repair.protocol"),
        (bool(candidate_ids),
         lambda answer: material_selection_error(answer, candidate_ids, prior_decisions),
         "scene.creator.material-selection-repair.protocol"),
    )
    for enabled, check, layer_id in checks:
        if not enabled:
            continue
        issue = check(payload)
        if issue:
            prompt += "\n\n" + prompt_layer_spec(layer_id).default_text
            payload = invoke(prompt)
            issue = check(payload)
        if issue:
            raise ValueError(issue)
    return payload, prompt


__all__ = ["initial_material_choice_error", "material_selection_error", "repair_material_choice"]
