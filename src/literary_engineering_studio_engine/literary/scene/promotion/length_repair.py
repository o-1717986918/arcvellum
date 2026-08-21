"""Prompt-facing projection of a deterministic target-length repair allocation."""

from __future__ import annotations

from typing import Any

from ...planning.length_repair import TARGET_LENGTH_REPAIR_SCHEMA


def target_length_repair_input(
    review_payload: dict[str, Any],
    scene_id: str,
) -> dict[str, Any]:
    if str(review_payload.get("schema") or "") != TARGET_LENGTH_REPAIR_SCHEMA:
        return {}
    allocation = _scene_allocation(review_payload, scene_id)
    if not allocation:
        return {}
    contract = review_payload.get("creative_contract")
    contract = contract if isinstance(contract, dict) else {}
    return {
        "scene_id": scene_id,
        "current_scene_chars": int(allocation.get("current_scene_chars") or 0),
        "required_growth_chars": int(allocation.get("required_growth_chars") or 0),
        "minimum_scene_chars": int(allocation.get("minimum_scene_chars") or 0),
        "max_scene_chars": int(allocation.get("max_scene_chars") or 0),
        "scene_function": str(allocation.get("scene_function") or ""),
        "repair_focus": str(allocation.get("repair_focus") or ""),
        "required": _string_list(contract.get("required")),
        "forbidden": _string_list(contract.get("forbidden")),
    }


def target_length_instruction(contract: dict[str, Any]) -> str:
    if not contract:
        return ""
    minimum = int(contract.get("minimum_scene_chars") or 0)
    growth = int(contract.get("required_growth_chars") or 0)
    maximum = int(contract.get("max_scene_chars") or 0)
    return (
        f"本次全书目标长度返工要求清洁正文至少达到 {minimum} 个中文内容字符，"
        f"相对正式场景净增至少 {growth}，且不得超过 {maximum or '当前场景上限'}。"
        "新增内容必须承担因果动作、关系压力、信息释放、行动后果或必要余波；"
        "禁止重复心理、景物堆叠、同义复述和对白注水。"
    )


def _scene_allocation(payload: dict[str, Any], scene_id: str) -> dict[str, Any]:
    allocations = payload.get("allocations")
    if not isinstance(allocations, list):
        return {}
    for item in allocations:
        if isinstance(item, dict) and str(item.get("scene_id") or "") == scene_id:
            return dict(item)
    return {}


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


__all__ = ["target_length_instruction", "target_length_repair_input"]
