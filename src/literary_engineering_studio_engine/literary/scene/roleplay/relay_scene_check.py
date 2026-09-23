"""Narrow scene-outcome evidence contract after an open character relay."""

from __future__ import annotations

import json
from typing import Any

from .relay_plan import RELAY_PLAN_SCHEMA


RELAY_SCENE_CHECK_SCHEMA = "arcvellum/scene-relay-check/v1"
_STATUSES = frozenset({"fulfilled", "missing", "uncertain"})


def render_relay_scene_check_prompt(plan: dict[str, Any], actor_entries: list[dict[str, Any]]) -> str:
    """Ask the main creator to inspect a completed interaction segment, not direct a turn."""

    milestones, entries = _check_inputs(plan, actor_entries)
    evidence = [{key: entry[key] for key in (
        "entry_id", "speaker", "spoken", "first_person_action", "private_impulse",
    )} for entry in entries]
    return f"""# Scene Relay Outcome Check

你是唯一主创，只在一段角色真实互动结束后核对本场既定结果。你不写对白、动作、正文、下一轮角色任务，也不评价文风。只依据下列一级角色条目判断每个 source_quote 是否已经真正发生；任务单中的结果本身不是发生证据。

说出口的承认必须见于该角色 spoken，可见行动必须见于其 first_person_action；仅仅在 private_impulse 里想说或想做不算。只有 source_quote 明确描述角色自己的内在认知变化时，private_impulse 才能作为该角色的证据。角色主观说法不自动证明未获来源支持的世界事实。证据不足就标 missing，存在但有歧义就标 uncertain，不替角色补完，也不因为情节需要而判 fulfilled。

## 已锁定的场景结果
{json.dumps(milestones, ensure_ascii=False)}

## 按真实发生顺序的角色条目
{json.dumps(evidence, ensure_ascii=False)}

仅返回 JSON：{{"scene_id":"{plan['scene_id']}","results":[{{"milestone_id":"m1","status":"fulfilled|missing|uncertain","evidence_entry_ids":["仅引用上面的 entry_id"]}}]}}。results 须覆盖全部 milestone 且顺序一致；fulfilled 须给出属于该结果归属角色的明确证据，missing 的证据列表为空。"""


def parse_relay_scene_check(
    payload: dict[str, Any], plan: dict[str, Any], actor_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    milestones, entries = _check_inputs(plan, actor_entries)
    if not isinstance(payload, dict) or payload.get("scene_id") != plan["scene_id"]:
        raise ValueError("relay scene check scene_id mismatch")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(milestones):
        raise ValueError("relay scene check must cover all milestones")
    by_id = {entry["entry_id"]: entry for entry in entries}
    normalized = [
        _check_result(result, milestone, by_id)
        for result, milestone in zip(results, milestones, strict=True)
    ]
    return {"schema": RELAY_SCENE_CHECK_SCHEMA, "scene_id": plan["scene_id"], "results": normalized}


def _check_inputs(
    plan: dict[str, Any], actor_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not isinstance(plan, dict) or plan.get("schema") != RELAY_PLAN_SCHEMA or not plan.get("scene_id"):
        raise ValueError("relay scene check requires a parsed relay plan")
    milestones = plan.get("milestones")
    if not isinstance(milestones, list) or not 1 <= len(milestones) <= 4:
        raise ValueError("relay scene check requires one to four milestones")
    if not isinstance(actor_entries, list) or len(actor_entries) > 24:
        raise ValueError("relay scene check entries exceed limit")
    participants = {item.get("speaker") for item in plan.get("actor_knowledge", []) if isinstance(item, dict)}
    normalized = [_normalize_check_entry(item, participants) for item in actor_entries]
    if len({item["entry_id"] for item in normalized}) != len(normalized):
        raise ValueError("relay scene check entry_id must be unique")
    return milestones, normalized


def _normalize_check_entry(item: Any, participants: set[str]) -> dict[str, str]:
    if not isinstance(item, dict) or item.get("speaker") not in participants:
        raise ValueError("relay scene check entry speaker mismatch")
    entry_id = item.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id or len(entry_id) > 100:
        raise ValueError("relay scene check entry_id is invalid")
    fields = {key: item.get(key, "") for key in ("spoken", "first_person_action", "private_impulse")}
    if any(not isinstance(value, str) for value in fields.values()):
        raise ValueError("relay scene check entry text is invalid")
    return {"entry_id": entry_id, "speaker": item["speaker"], **fields}


def _check_result(
    result: Any, milestone: dict[str, str], by_id: dict[str, dict[str, str]],
) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("milestone_id") != milestone["milestone_id"]:
        raise ValueError("relay scene check milestone order mismatch")
    status = result.get("status")
    ids = result.get("evidence_entry_ids")
    if status not in _STATUSES or not isinstance(ids, list) or len(ids) > 4:
        raise ValueError("relay scene check status or evidence is invalid")
    if any(not isinstance(item, str) or item not in by_id for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("relay scene check evidence_entry_ids must reference unique known entries")
    if status == "missing" and ids:
        raise ValueError("relay scene check missing result cannot cite evidence")
    if status == "fulfilled" and not any(by_id[item]["speaker"] == milestone["speaker"] for item in ids):
        raise ValueError("relay scene check fulfilled result requires owner evidence")
    return {"milestone_id": milestone["milestone_id"], "status": status, "evidence_entry_ids": ids}


__all__ = ["RELAY_SCENE_CHECK_SCHEMA", "render_relay_scene_check_prompt", "parse_relay_scene_check"]
