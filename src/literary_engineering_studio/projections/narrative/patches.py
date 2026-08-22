"""Digest-bound incremental transport for narrative projection v3."""

from __future__ import annotations

from typing import Any


PATCH_SCHEMA = "arcvellum/narrative-projection-patch/v1"
_TRANSPORT_FIELDS = {
    "nodes",
    "edges",
    "delta",
    "motion_events",
    "revision",
    "projection_revision",
    "sequence",
    "schema",
}


def build_projection_patch(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    sequence: int,
    delta: dict[str, Any],
    motion_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe one exact transition without repeating the full graph."""

    previous_nodes = _index(previous.get("nodes"), "node_id")
    current_nodes = _index(current.get("nodes"), "node_id")
    previous_edges = _index(previous.get("edges"), "edge_id")
    current_edges = _index(current.get("edges"), "edge_id")
    node_order = list(current_nodes)
    edge_order = list(current_edges)
    previous_meta = _projection_meta(previous)
    current_meta = _projection_meta(current)
    return {
        "ok": True,
        "schema": PATCH_SCHEMA,
        "projection_schema": str(current.get("schema") or previous.get("schema") or ""),
        "base_revision": _revision(previous),
        "target_revision": _revision(current),
        "sequence": int(sequence),
        "meta": {
            key: value
            for key, value in current_meta.items()
            if key not in previous_meta or previous_meta[key] != value
        },
        "meta_remove": [key for key in previous_meta if key not in current_meta],
        "nodes": _collection_patch(previous_nodes, current_nodes, node_order),
        "edges": _collection_patch(previous_edges, current_edges, edge_order),
        "delta": delta,
        "motion_events": motion_events,
    }


def apply_projection_patch(
    previous: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a patch atomically or reject a mismatched transition."""

    if str(patch.get("schema") or "") != PATCH_SCHEMA:
        raise ValueError("unsupported narrative projection patch")
    if _revision(previous) != str(patch.get("base_revision") or ""):
        raise ValueError("narrative projection patch base revision mismatch")
    target_revision = str(patch.get("target_revision") or "")
    if not target_revision:
        raise ValueError("narrative projection patch target revision is missing")
    result = dict(previous)
    for key in patch.get("meta_remove") or []:
        result.pop(str(key), None)
    meta = patch.get("meta")
    if isinstance(meta, dict):
        result.update(meta)
    result.update(
        {
            "ok": True,
            "schema": str(patch.get("projection_schema") or previous.get("schema") or ""),
            "revision": target_revision,
            "projection_revision": target_revision,
            "sequence": int(patch.get("sequence") or 0),
            "nodes": _apply_collection(previous.get("nodes"), patch.get("nodes"), "node_id"),
            "edges": _apply_collection(previous.get("edges"), patch.get("edges"), "edge_id"),
            "delta": patch.get("delta") if isinstance(patch.get("delta"), dict) else {},
            "motion_events": patch.get("motion_events") if isinstance(patch.get("motion_events"), list) else [],
        }
    )
    return result


def _collection_patch(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    order: list[str],
) -> dict[str, Any]:
    upsert = [
        item
        for key, item in current.items()
        if key not in previous or previous[key] != item
    ]
    removed = [key for key in previous if key not in current]
    previous_order = list(previous)
    return {
        "upsert": upsert,
        "remove": removed,
        "order": order if order != previous_order else [],
    }


def _projection_meta(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in projection.items()
        if key not in _TRANSPORT_FIELDS
    }


def _apply_collection(items: Any, patch: Any, key_name: str) -> list[dict[str, Any]]:
    current = _index(items, key_name)
    if not isinstance(patch, dict):
        raise ValueError(f"narrative projection {key_name} patch is missing")
    for key in patch.get("remove") or []:
        current.pop(str(key), None)
    for item in _valid_upserts(patch.get("upsert"), key_name):
        current[str(item[key_name])] = item
    order = _ordered_keys(current, patch.get("order"))
    return [current[key] for key in order]


def _valid_upserts(items: Any, key_name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get(key_name) or ""):
            raise ValueError(f"narrative projection {key_name} upsert is invalid")
        result.append(item)
    return result


def _ordered_keys(current: dict[str, dict[str, Any]], requested: Any) -> list[str]:
    order = [str(key) for key in requested if str(key) in current] if isinstance(requested, list) else []
    if not order:
        return list(current)
    known = set(order)
    return [*order, *[key for key in current if key not in known]]


def _index(items: Any, key_name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and str(item.get(key_name) or ""):
            result[str(item[key_name])] = item
    return result


def _revision(projection: dict[str, Any]) -> str:
    return str(projection.get("projection_revision") or projection.get("revision") or "")
