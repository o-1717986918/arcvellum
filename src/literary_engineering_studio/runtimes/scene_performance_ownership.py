"""Narrow dialogue and visible-action provenance for first-level performers."""

from __future__ import annotations

import json
import re
from typing import Any, Callable


_QUOTED = re.compile(r"[“「]([^”」]+)[”」]")
_LETTERS = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")
_DIALOGUE_TAG = re.compile(r"(?:说|问|答|道|喊|叫|开口|应声|继续)[，,:：]?$|[：:]$")


def unlicensed_scene_dialogue(prose: str, materials: str) -> list[str]:
    """Find quoted text absent from every first-level actor's spoken material.

    This intentionally does not judge prose quality or infer visible-action semantics.
    """

    if not materials:
        return []
    entries = _material_entries(materials)
    spoken = [_normalize(entry.get("spoken", "")) for entry in entries]
    missing = []
    for match in _QUOTED.finditer(prose):
        paragraph_start = prose.rfind("\n", 0, match.start()) + 1
        prefix = prose[paragraph_start:match.start()].strip()
        if prefix and not _DIALOGUE_TAG.search(prefix):
            continue
        quote = match.group(1).strip()
        normalized = _normalize(quote)
        if normalized and not any(normalized in source for source in spoken):
            missing.append(quote)
    return list(dict.fromkeys(missing))


def audit_visible_actions(
    prose: str, materials: str, invoke: Callable[[str], str],
) -> list[dict[str, str]]:
    """Ask a focused reviewer about consequential visible acts, not literary taste."""

    entries = _material_entries(materials)
    prompt = _action_audit_prompt(prose, entries)
    try:
        payload = json.loads(invoke(prompt))
    except json.JSONDecodeError as exc:
        raise ValueError("visible-action audit did not return JSON") from exc
    return _validated_action_findings(payload, prose, entries)


def _action_audit_prompt(prose: str, entries: list[dict[str, Any]]) -> str:
    sources = [{key: entry.get(key, "") for key in ("entry_id", "speaker", "first_person_action", "spoken")}
               for entry in entries]
    return (
        "# First-Level Visible Action Source Audit\n\n"
        "只核对小说候选里在场人物已经实际做出的可见动作是否由同一人物的 first_person_action 支持。"
        "从头到尾逐段找出每个人的动态行为，再逐项对照来源；拿起、放下、触碰、转身、走近、离场、"
        "手势、明确朝某处看一眼，即使不改变物件状态也算动作。"
        "同一动作换人称、词序或措辞仍算有来源：‘把手从信封上松开’支持‘他松开信封’，绝不可报违规。"
        "‘没碰信’不支持‘拿起信’，‘按紧信’也不支持‘朝抽屉看一眼’。"
        "单纯‘看见／看着’是视角感知，台词间停顿可来自 spoken；环境观察、静态姿态、主观猜测、"
        "明确没做的事也不是新增外显动作。不要审文风、篇幅、数字或对白。"
        "每条问题必须说出来源缺少的具体新动作；若最接近条目已在语义上覆盖它，删除该问题。"
        "只引用正文的精确连续短句，speaker 必须逐字抄自实施动作的角色条目，不写别称；若有最接近的同角色条目，"
        "填其 entry_id，否则填空串。没有越权就返回空列表。\n\n"
        f"一级角色言行：{json.dumps(sources, ensure_ascii=False)}\n\n"
        f"候选正文：{prose}\n\n"
        "只返回 JSON：{\"status\":\"clean|violations_found\",\"violations\":["
        "{\"prose_quote\":\"正文精确短句\",\"speaker\":\"人物名\","
        "\"closest_entry_id\":\"条目 ID 或空串\",\"why_not_covered\":\"来源与额外动作的差别\"}]}。"
    )


def _validated_action_findings(payload: Any, prose: str, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(payload, dict) or payload.get("status") not in {"clean", "violations_found"}:
        raise ValueError("visible-action audit has invalid status")
    violations = payload.get("violations")
    if not isinstance(violations, list) or len(violations) > 24:
        raise ValueError("visible-action audit has invalid violations")
    if bool(violations) != (payload["status"] == "violations_found"):
        raise ValueError("visible-action audit status conflicts with findings")
    speakers = {str(entry.get("speaker") or "") for entry in entries}
    by_id = {str(entry.get("entry_id") or ""): str(entry.get("speaker") or "")
             for entry in entries if entry.get("entry_id")}
    for item in violations:
        _validate_action_finding(item, prose, speakers, by_id)
    return violations


def _validate_action_finding(item: Any, prose: str, speakers: set[str], by_id: dict[str, str]) -> None:
    if not isinstance(item, dict):
        raise ValueError("visible-action audit finding must be an object")
    quote, speaker, closest, reason = (item.get(key) for key in
                                       ("prose_quote", "speaker", "closest_entry_id", "why_not_covered"))
    if (not isinstance(quote, str) or not quote.strip() or quote not in prose
            or not isinstance(speaker, str) or speaker not in speakers
            or not isinstance(closest, str) or (closest and by_id.get(closest) != speaker)
            or not isinstance(reason, str) or not reason.strip()):
        raise ValueError("visible-action audit finding lacks exact same-actor evidence")


def ownership_repair_instruction(kind: str, evidence: list[str]) -> str:
    opening = (
        "删除以下没有一级角色 first_person_action 来源的可见动作，不得把动作改成主创代做的另一动作；"
        if kind == "action" else
        "删除以下不在任何角色 spoken 中的引号内台词，不得改写成另一句主创代说的话；"
    )
    return (opening + "保留已获授权的角色言行及有效心理和环境。若因此缺少场景表演，"
            "在 escalation_reasons 请求原角色续演：" + json.dumps(evidence[:8], ensure_ascii=False))


def repair_actor_ownership(
    candidate: Any, materials: str, audit: Callable[[str], list[dict[str, str]]],
    revise: Callable[[Any, str, list[str]], Any],
) -> Any:
    """Bound repair across both ownership checks; never claim semantic certainty."""

    if not materials:
        return candidate
    for attempt in range(5):
        missing = unlicensed_scene_dialogue(candidate.prose, materials)
        if missing:
            kind, evidence = "dialogue", missing
        else:
            violations = audit(candidate.prose)
            if not violations:
                return candidate
            kind = "action"
            evidence = [f"{item['speaker']}：{item['prose_quote']}｜{item['why_not_covered']}"
                        for item in violations]
        if attempt == 4:
            raise RuntimeError("scene writer retained first-level actor ownership violations after four repairs")
        candidate = revise(candidate, kind, evidence)
    raise AssertionError("unreachable ownership repair state")


def _material_entries(materials: str) -> list[dict[str, Any]]:
    try:
        packet = json.loads(materials.split("\n", 1)[1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("first-level performance material block is malformed") from exc
    entries = _actor_entries(packet)
    if not entries:
        raise ValueError("first-level performance material block has no actor entries")
    return entries


def _actor_entries(packet: Any) -> list[dict[str, Any]]:
    if not isinstance(packet, dict):
        return []
    if isinstance(packet.get("actor_entries"), list):
        return [item for item in packet["actor_entries"] if isinstance(item, dict)]
    groups = packet.get("actor_candidates")
    if not isinstance(groups, list):
        return []
    return [{**entry, "speaker": str(group.get("speaker") or ""),
             "entry_id": entry.get("entry_id") or f"batch:{group_index + 1}:{entry_index + 1}"}
            for group_index, group in enumerate(groups) if isinstance(group, dict)
            for entry_index, entry in enumerate(group.get("entries", [])) if isinstance(entry, dict)]


def _normalize(text: Any) -> str:
    return _LETTERS.sub("", text) if isinstance(text, str) else ""


__all__ = ["audit_visible_actions", "ownership_repair_instruction", "repair_actor_ownership", "unlicensed_scene_dialogue"]
