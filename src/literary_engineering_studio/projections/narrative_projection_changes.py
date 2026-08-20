"""Revision deltas, motion events and timeline projections."""

from __future__ import annotations

from typing import Any


def projection_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    previous_nodes = _items_by_id((previous or {}).get("nodes"), "node_id")
    current_nodes = _items_by_id(current.get("nodes"), "node_id")
    previous_edges = _items_by_id((previous or {}).get("edges"), "edge_id")
    current_edges = _items_by_id(current.get("edges"), "edge_id")
    return {
        "initial": previous is None,
        "added_nodes": sorted(current_nodes.keys() - previous_nodes.keys()),
        "removed_nodes": sorted(previous_nodes.keys() - current_nodes.keys()),
        "updated_nodes": _changed_ids(previous_nodes, current_nodes),
        "added_edges": sorted(current_edges.keys() - previous_edges.keys()),
        "removed_edges": sorted(previous_edges.keys() - current_edges.keys()),
        "updated_edges": _changed_ids(previous_edges, current_edges),
    }


def projection_motion_events(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    delta: dict[str, Any],
) -> list[dict[str, str]]:
    current_nodes = _items_by_id(current.get("nodes"), "node_id", require_id=False)
    previous_nodes = _items_by_id((previous or {}).get("nodes"), "node_id", require_id=False)
    events = _added_events(current_nodes, delta.get("added_nodes"))
    events.extend(_updated_events(previous_nodes, current_nodes, delta.get("updated_nodes")))
    task_event = _task_event(current.get("nodes"))
    if task_event:
        events.append(task_event)
    return events[:12]


def timeline(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(nodes, key=lambda item: (int(item.get("order") or 0), str(item.get("node_id") or "")))
    return [_timeline_item(item) for item in ordered if item.get("type") in {"chapter", "scene"}]


def _items_by_id(value: object, key: str, *, require_id: bool = True) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get(key) or "")
        if item_id or not require_id:
            result[item_id] = item
    return result


def _changed_ids(previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(item_id for item_id in current.keys() & previous.keys() if current[item_id] != previous[item_id])


def _added_events(current: dict[str, dict[str, Any]], node_ids: object) -> list[dict[str, str]]:
    events = []
    for node_id in node_ids if isinstance(node_ids, list) else []:
        node = current.get(str(node_id), {})
        event_type = "branch-grown" if node.get("type") == "branch" else "node-grown"
        events.append({"type": event_type, "node_id": str(node_id), "label": str(node.get("label") or "新叙事节点")})
    return events


def _updated_events(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    node_ids: object,
) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for node_id in node_ids if isinstance(node_ids, list) else []:
        before = previous.get(str(node_id), {})
        after = current.get(str(node_id), {})
        events.extend(_node_update_events(str(node_id), before, after))
    return events


def _node_update_events(
    node_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    if after.get("status") == "formal" and before.get("status") != "formal":
        events.append({"type": "joined-canon", "node_id": node_id, "label": str(after.get("label") or "并入正式长卷")})
    before_chars = _metric_integer(before, "formal_chars")
    after_chars = _metric_integer(after, "formal_chars")
    if after_chars > before_chars:
        events.append({"type": "manuscript-grown", "node_id": node_id, "label": f"正文增加 {after_chars - before_chars:,} 字"})
    if after.get("type") == "canon" and after.get("status") == "formal":
        events.append({"type": "canon-anchored", "node_id": node_id, "label": str(after.get("label") or "设定已写回")})
    return events


def _task_event(nodes: object) -> dict[str, str] | None:
    for item in nodes if isinstance(nodes, list) else []:
        if isinstance(item, dict) and item.get("type") == "task" and item.get("status") == "queued":
            return {"type": "task-pulse", "node_id": str(item.get("node_id") or ""), "label": str(item.get("subtitle") or "当前任务")}
    return None


def _metric_integer(node: dict[str, Any], key: str) -> int:
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    return int(metrics.get(key) or 0)


def _timeline_item(item: dict[str, Any]) -> dict[str, Any]:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    return {
        "node_id": str(item.get("node_id") or ""), "label": str(item.get("label") or ""),
        "status": str(item.get("status") or "planned"), "order": int(item.get("order") or 0),
        "formal_chars": int(metrics.get("formal_chars") or 0),
        "word_target": int(metrics.get("word_target") or 0),
    }


__all__ = ["projection_delta", "projection_motion_events", "timeline"]
