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
    """Ask one focused reviewer about consequential new actor turns, not literary taste."""

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
        "只核对在场人物已做出的、会改变情节或关系的关键可见动作是否由同一人物的 first_person_action 支持。"
        "同时核对承担情节转折的直接引语回合是否由同一人物的 spoken 支持。"
        "主创可以改写已有台词的措辞、长短和语势；同一意图与互动位置仍算有来源。"
        "演员只在私念中想过、只做过动作或后来才说出另一件事，都不能给本处新增发言回合提供 spoken 来源。"
        "重点是决定性交付、藏取证物、揭露线索、伤害、离开冲突或以行动作出承诺。"
        "同一动作换人称、词序或措辞仍算有来源：‘把手从信封上松开’支持‘他松开信封’，绝不可报违规。"
        "‘没碰信’不支持‘拿起信并藏入衣袋’。"
        "普通走位、拿放无情节后果的道具、眼神、手势、台词间停顿和视角感知属于主创的场面组织，"
        "不作为违规；环境观察、静态姿态、主观猜测和明确没做的事也不报。不要审文风、篇幅或数字。"
        "每条问题必须说出来源缺少的具体新动作或新发言回合；若最接近条目已在语义上覆盖它，删除该问题。"
        "只引用正文的精确连续短句，speaker 必须逐字抄自实施动作的角色条目，不写别称；若有最接近的同角色条目，"
        "填其 entry_id，否则填空串。没有越权就返回空列表。\n\n"
        f"一级角色言行：{json.dumps(sources, ensure_ascii=False)}\n\n"
        f"候选正文：{prose}\n\n"
        "只返回 JSON：{\"status\":\"clean|violations_found\",\"violations\":["
        "{\"kind\":\"action|dialogue\",\"prose_quote\":\"正文精确短句\",\"speaker\":\"人物名\","
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
    return _grounded_action_findings(violations, prose, speakers, by_id)


def _grounded_action_findings(
    violations: list[Any], prose: str, speakers: set[str], by_id: dict[str, str],
) -> list[dict[str, str]]:
    valid = []
    first_error: ValueError | None = None
    for item in violations:
        try:
            _validate_action_finding(item, prose, speakers, by_id)
        except ValueError as exc:
            first_error = first_error or exc
            continue
        valid.append(item)
    # A reviewer can append a fictitious example to otherwise grounded findings.
    # Keep the supported findings so the author can repair them, but never turn
    # an entirely ungrounded "violations_found" response into a clean pass.
    if violations and not valid and first_error is not None:
        raise first_error
    return valid


def _validate_action_finding(item: Any, prose: str, speakers: set[str], by_id: dict[str, str]) -> None:
    if not isinstance(item, dict):
        raise ValueError("visible-action audit finding must be an object")
    quote, speaker, closest, reason = (item.get(key) for key in
                                       ("prose_quote", "speaker", "closest_entry_id", "why_not_covered"))
    kind = item.get("kind", "action")
    if (kind not in {"action", "dialogue"}
            or not isinstance(quote, str) or not quote.strip() or quote not in prose
            or not isinstance(speaker, str) or speaker not in speakers
            or not isinstance(closest, str) or (closest and by_id.get(closest) != speaker)
            or not isinstance(reason, str) or not reason.strip()):
        raise ValueError("visible-action audit finding lacks exact same-actor evidence")


def ownership_repair_instruction(kind: str, evidence: list[str]) -> str:
    opening = (
        "以下关键可见动作缺少一级角色 first_person_action 来源；若本场需要这些动作，优先通过 material_requests 请原角色续演，若不需要则删除；"
        if kind == "action" else
        "以下关键发言回合缺少同一角色 spoken 的意图与互动位置来源；若本场需要这些话，先通过 material_requests 请原角色续演，若不需要则删除；已有回合仍可改写措辞；"
    )
    return (opening + "保留已获授权的角色言行及有效心理和环境。"
            "需补充角色行为时请求原角色续演：" + json.dumps(evidence[:8], ensure_ascii=False))


def repair_actor_ownership(
    candidate: Any, materials: str | Callable[[], str], audit: Callable[[str], list[dict[str, str]]],
    revise: Callable[[Any, str, list[str]], Any],
    *, allow_dialogue_rewrite: bool = False,
) -> Any:
    """Bound repair across both ownership checks; never claim semantic certainty."""

    current_materials = materials() if callable(materials) else materials
    if not current_materials or not has_actor_entries(current_materials):
        return candidate
    for attempt in range(5):
        current_materials = materials() if callable(materials) else materials
        missing = [] if allow_dialogue_rewrite else unlicensed_scene_dialogue(candidate.prose, current_materials)
        if missing:
            kind, evidence = "dialogue", missing
        else:
            violations = audit(candidate.prose)
            if not violations:
                return candidate
            kind = "dialogue" if any(item.get("kind") == "dialogue" for item in violations) else "action"
            selected = [item for item in violations if item.get("kind", "action") == kind]
            evidence = [f"{item['speaker']}：{item['prose_quote']}｜{item['why_not_covered']}"
                        for item in selected]
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


def compact_performance_materials(materials: str) -> str:
    """Keep original actor evidence for revision without repeating the full rehearsal plan."""

    if not materials:
        return ""
    try:
        packet = json.loads(materials.split("\n", 1)[1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("first-level performance material block is malformed") from exc
    if not isinstance(packet, dict):
        raise ValueError("first-level performance material block is malformed")
    compact = {key: packet[key] for key in ("environment_candidates", "environment") if key in packet}
    compact["actor_entries"] = [
        {key: entry[key] for key in ("entry_id", "beat_id", "speaker", "spoken", "first_person_action") if key in entry}
        for entry in _actor_entries(packet)
    ]
    if not _actor_entries(compact) and not compact.get("environment_candidates") and not compact.get("environment"):
        raise ValueError("first-level performance material block has no actor entries")
    return "一级言行与环境候选；省略已用过的初始化、任务和逐轮提示。\n" + json.dumps(
        compact, ensure_ascii=False, separators=(",", ":"))


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


def has_actor_entries(materials: str) -> bool:
    if not materials:
        return False
    try:
        packet = json.loads(materials.split("\n", 1)[1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("first-level performance material block is malformed") from exc
    return bool(_actor_entries(packet))


def _normalize(text: Any) -> str:
    return _LETTERS.sub("", text) if isinstance(text, str) else ""


__all__ = ["audit_visible_actions", "compact_performance_materials", "has_actor_entries", "ownership_repair_instruction", "repair_actor_ownership", "unlicensed_scene_dialogue"]
