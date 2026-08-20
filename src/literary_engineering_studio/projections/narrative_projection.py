"""Stable, rebuildable graph projection of formal narrative evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .core_read_models import build_dashboard, build_library
from .narrative_projection_changes import projection_delta, projection_motion_events, timeline
from .narrative_projection_evidence import append_scene_evidence, append_task_projection
from .narrative_projection_graphs import book_graph, chapter_graph, scene_graph
from .narrative_projection_models import ProjectionInventory
from .narrative_projection_primitives import (
    accessible_summary,
    chapter_label,
    dedupe_edges,
    dedupe_nodes,
    digest,
    edge,
    fact,
    formal_chars_by_chapter,
    friendly_action,
    integer,
    node,
    order,
    resolve_focus,
    scene_chapter,
)
from .reader import build_reader_manifest


PROJECTION_SCHEMA = "arcvellum/narrative-projection/v2"
LEVELS = {"book", "chapter", "scene"}


def build_narrative_projection(
    config: dict[str, Any],
    project_root: Path,
    *,
    level: str = "book",
    focus: str = "",
    dashboard_payload: dict[str, Any] | None = None,
    library_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    selected_level = level if level in LEVELS else "book"
    library = library_payload if isinstance(library_payload, dict) else build_library(config, root)
    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else build_dashboard(config, root)
    reader = build_reader_manifest(root)
    inventory = ProjectionInventory.from_library(library)
    focus_id = resolve_focus(selected_level, focus, inventory.scenes, dashboard)
    nodes, edges = _graph_for_level(selected_level, inventory, reader, dashboard, focus_id)
    nodes, edges = _normalize_graph(nodes, edges)
    return _projection_payload(root, selected_level, focus_id, inventory, reader, nodes, edges)


def _graph_for_level(
    level: str,
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    dashboard: dict[str, Any],
    focus: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if level == "book":
        return book_graph(inventory, reader, dashboard)
    if level == "chapter":
        return chapter_graph(inventory, reader, dashboard, focus)
    return scene_graph(inventory, reader, dashboard, focus)


def _normalize_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique_nodes = dedupe_nodes(nodes)
    node_ids = {str(item["node_id"]) for item in unique_nodes}
    unique_edges = [item for item in dedupe_edges(edges) if item["source"] in node_ids and item["target"] in node_ids]
    return unique_nodes, unique_edges


def _projection_payload(
    root: Path,
    level: str,
    focus: str,
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    projection = {
        "ok": True,
        "schema": PROJECTION_SCHEMA,
        "project_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": _projection_revision(nodes, edges),
        "sequence": 0,
        "level": level,
        "focus": focus,
        "summary": {
            "node_count": len(nodes), "edge_count": len(edges), "scene_count": len(inventory.scenes),
            "formal_prose_chars": int(reader.get("total_chinese_content_chars") or 0),
            "aggregated": level == "book" and len(inventory.scenes) > 80,
        },
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline(nodes),
        "motion_events": [],
        "legend": _legend(),
        "accessibility_summary": accessible_summary(level, nodes, edges),
    }
    projection["delta"] = projection_delta(None, projection)
    return projection


def _projection_revision(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    value = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _legend() -> list[dict[str, str]]:
    return [
        {"type": "current", "label": "正在推进", "color": "jade"},
        {"type": "formal", "label": "正式正文与记忆", "color": "brass"},
        {"type": "blocked", "label": "阻塞或待决定", "color": "cinnabar"},
        {"type": "alternative", "label": "备选与不确定", "color": "iris"},
        {"type": "queued", "label": "下一项状态机任务", "color": "moss"},
    ]


# Stable private names retained for downstream integrations that predate the split.
def _book_graph(scenes, characters, reader, dashboard):
    return book_graph(ProjectionInventory(scenes, characters, [], [], []), reader, dashboard)


def _chapter_graph(scenes, characters, branches, reviews, canon_patches, reader, dashboard, chapter_id):
    return chapter_graph(ProjectionInventory(scenes, characters, branches, reviews, canon_patches), reader, dashboard, chapter_id)


def _scene_graph(scenes, characters, branches, reviews, canon_patches, reader, dashboard, scene_id):
    return scene_graph(ProjectionInventory(scenes, characters, branches, reviews, canon_patches), reader, dashboard, scene_id)


def _append_scene_evidence(nodes, edges, scene, branches, reviews, canon_patches, *, include_pending):
    inventory = ProjectionInventory([], [], branches, reviews, canon_patches)
    return append_scene_evidence(nodes, edges, scene, inventory, include_pending=include_pending)


_append_task_projection = append_task_projection
_formal_chars_by_chapter = formal_chars_by_chapter
_timeline = timeline
_node = node
_edge = edge
_resolve_focus = resolve_focus
_scene_chapter = scene_chapter
_fact = fact
_dedupe = dedupe_nodes
_dedupe_edges = dedupe_edges
_order = order
_integer = integer
_chapter_label = chapter_label
_digest = digest
_friendly_action = friendly_action


def _accessible_summary(level, focus, nodes, edges):
    del focus
    return accessible_summary(level, nodes, edges)


__all__ = ["build_narrative_projection", "projection_delta", "projection_motion_events"]
