"""Deterministic node, relation and source helpers for narrative projections."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def node(
    node_id: str,
    node_type: str,
    label: str,
    status: str,
    source_type: str,
    source_id: str,
    navigate: str,
    *,
    subtitle: str = "",
    metrics: dict[str, Any] | None = None,
    order: int = 0,
) -> dict[str, Any]:
    return {
        "node_id": node_id, "type": node_type, "label": label, "subtitle": subtitle,
        "status": status, "source_type": source_type, "source_id": source_id,
        "navigate": navigate, "metrics": metrics or {}, "order": order,
    }


def edge(source: str, target: str, edge_type: str, label: str) -> dict[str, str]:
    return {
        "edge_id": f"{edge_type}:{source}>{target}",
        "source": source, "target": target, "type": edge_type, "label": label,
    }


def resolve_focus(level: str, focus: str, scenes: list[dict[str, Any]], dashboard: dict[str, Any]) -> str:
    if focus:
        return focus
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    target = next(
        (str(item.get("target")) for item in actions if isinstance(item, dict) and str(item.get("target", "")).startswith("scene")),
        "",
    )
    if level == "scene":
        return target or (str(scenes[0].get("id")) if scenes else "")
    if level == "chapter":
        scene = next((item for item in scenes if str(item.get("id")) == target), scenes[0] if scenes else {})
        return scene_chapter(scene)
    return "book"


def scene_chapter(scene: dict[str, Any]) -> str:
    return fact(scene, "章节") or str(scene.get("subtitle") or "未分章")


def fact(item: dict[str, Any], label: str) -> str:
    facts = item.get("facts") if isinstance(item.get("facts"), list) else []
    for item_fact in facts:
        if isinstance(item_fact, dict) and str(item_fact.get("label")) == label:
            return str(item_fact.get("value") or "")
    return ""


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in nodes:
        result.setdefault(str(item["node_id"]), item)
    return list(result.values())


def dedupe_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for item in edges:
        result.setdefault(item["edge_id"], item)
    return list(result.values())


def order(value: str) -> tuple[int, str]:
    values = re.findall(r"\d+", value or "")
    return (int(values[-1]) if values else 10**9, value)


def integer(value: str) -> int:
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else 0


def chapter_label(chapter_id: str) -> str:
    number = order(chapter_id)[0]
    return f"第 {number} 章" if number < 10**9 else chapter_id


def digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:12]


def friendly_action(value: str) -> str:
    lowered = value.lower()
    labels = (
        ("context", "整理这一场所需的人物、设定和前情"),
        ("simulate-scene", "推演角色在当前处境中的选择"),
        ("branch-simulate", "比较可行的剧情分支"),
        ("compose-scene", "形成这一场的写作方案"),
        ("generate-scene", "创作这一场的正文"),
        ("agent-review-scene", "审读并核验这一场正文"),
        ("promote", "确认正文进入正式长卷"),
        ("state-evolve", "更新人物状态与剧情后果"),
    )
    for token, label in labels:
        if token in lowered:
            return label
    if "--" in value or lowered.startswith("lew ") or lowered.startswith("run "):
        return "状态机已准备好下一项创作工作"
    return value


def accessible_summary(level: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    blocked = sum(1 for item in nodes if item.get("status") == "blocked")
    formal = sum(1 for item in nodes if item.get("status") == "formal")
    level_label = {"book": "全书", "chapter": "全书章节", "scene": "全书场景"}.get(level, "叙事")
    return f"{level_label}视图，共 {len(nodes)} 个节点、{len(edges)} 条关系；{formal} 个正式节点，{blocked} 个阻塞或待决定节点。"


def formal_coverage(reader: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    units = reader.get("units") if isinstance(reader.get("units"), list) else []
    for unit in units:
        if isinstance(unit, dict):
            result.update(str(item) for item in unit.get("coverage", []))
    return result


def formal_chars_by_chapter(reader: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    units = reader.get("units") if isinstance(reader.get("units"), list) else []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        chapter_id = str(unit.get("chapter_id") or "")
        if chapter_id:
            result[chapter_id] = result.get(chapter_id, 0) + int(unit.get("chinese_content_chars") or 0)
    return result


__all__ = [
    "accessible_summary", "chapter_label", "dedupe_edges", "dedupe_nodes", "digest", "edge",
    "fact", "formal_chars_by_chapter", "formal_coverage", "friendly_action", "integer", "node",
    "order", "resolve_focus", "scene_chapter",
]
