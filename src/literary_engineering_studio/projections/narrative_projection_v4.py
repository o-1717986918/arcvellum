"""Project-wide creative constellation used by ArcVellum's spatial operating system."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import narrative_projection as narrative_projection_v2
from .narrative.characters import augment_character_graph, build_character_references
from .narrative.contracts import NarrativeFocusLevel
from .narrative.creative_constellation import (
    augment_creative_constellation,
    enrich_creative_nodes,
    project_activities,
)
from .narrative.grammar import SPATIAL_GRAMMARS, resolve_grammar
from .narrative.layout_hints import build_layout_hints
from .narrative.relations import build_focused_relations
from .narrative.revision import build_projection_revision, build_source_revisions
from .narrative_projection import projection_delta, projection_motion_events
from .narrative_projection_graphs import constellation_graph
from .narrative_projection_models import ProjectionInventory
from .narrative_projection_primitives import dedupe_edges, dedupe_nodes, resolve_focus
from .narrative_projection_v3 import (
    build_lod_summary,
    build_rhythm_hints,
    build_spatial_clusters,
    decorate_spatial_nodes,
)


PROJECTION_SCHEMA = "arcvellum/narrative-projection/v4"
NODE_DETAIL_SCHEMA = "arcvellum/narrative-node-detail/v2"


def build_narrative_projection_v4(
    config: dict[str, Any],
    project_root: Path,
    *,
    level: str = "book",
    focus: str = "",
    grammar: str = "auto",
    dashboard_payload: dict[str, Any] | None = None,
    library_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one graph; focus changes emphasis without changing graph membership."""

    root = project_root.resolve()
    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else narrative_projection_v2.build_dashboard(config, root)
    library = library_payload if isinstance(library_payload, dict) else narrative_projection_v2.build_library(config, root)
    reader = narrative_projection_v2.build_reader_manifest(root)
    inventory = ProjectionInventory.from_library(library)
    selected_level = NarrativeFocusLevel.parse(level)
    focus_id = _resolve_focus(selected_level, focus, inventory, dashboard)

    raw_nodes, raw_edges = constellation_graph(inventory, reader, dashboard)
    character_references = build_character_references(library)
    raw_nodes, raw_edges = augment_character_graph(raw_nodes, raw_edges, character_references)
    raw_nodes, raw_edges = augment_creative_constellation(
        raw_nodes,
        raw_edges,
        library=library,
        reader=reader,
        project_root=root,
        project_title=_project_title(root, config),
    )
    raw_nodes, raw_edges = _normalize_graph(raw_nodes, raw_edges)

    grammar_base = {"nodes": raw_nodes, "edges": raw_edges, "summary": {"scene_count": len(inventory.scenes)}}
    selected_grammar = resolve_grammar(grammar, grammar_base)
    rhythm_hints = build_rhythm_hints(root)
    nodes = decorate_spatial_nodes(
        raw_nodes,
        raw_edges,
        selected_grammar,
        rhythm_hints,
        detail_endpoint_prefix="/narrative/projection/v4/nodes",
    )
    nodes = enrich_creative_nodes(nodes, raw_edges)
    edges, focus_scope, relation_profiles = build_focused_relations(
        raw_edges,
        nodes,
        selected_level.value,
        focus_id,
    )
    clusters = build_spatial_clusters(nodes)

    base = narrative_projection_v2.build_narrative_projection(
        config,
        root,
        level="book",
        dashboard_payload=dashboard,
        library_payload=library,
    )
    references = [item.as_dict() for item in character_references]
    source_revisions = build_source_revisions(base, dashboard, library, reader, rhythm_hints, _digest)
    revision = build_projection_revision(
        base_revision=base.get("revision"),
        grammar=selected_grammar,
        nodes=nodes,
        edges=edges,
        clusters=clusters,
        focus_scope=focus_scope.as_dict(),
        relation_profiles=relation_profiles,
        character_references=references,
        source_revisions=source_revisions,
        digest=_digest,
    )
    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "scene_count": len(inventory.scenes),
        "chapter_count": sum(1 for item in nodes if item.get("creative_kind") == "chapter"),
        "formal_prose_chars": int(reader.get("total_chinese_content_chars") or 0),
        "interactive_node_count": sum(1 for item in nodes if item.get("available_actions")),
        "cluster_count": len(clusters),
        "spatial_grammar": selected_grammar,
        "whole_graph": True,
    }
    projection = {
        "ok": True,
        "schema": PROJECTION_SCHEMA,
        "project_root": str(root),
        "generated_at": base.get("generated_at"),
        "revision": revision,
        "projection_revision": revision,
        "sequence": 0,
        "source_revisions": source_revisions,
        "level": focus_scope.level.value,
        "focus": focus_scope.focus_id,
        "focus_scope": focus_scope.as_dict(),
        "relation_profiles": relation_profiles,
        "character_references": references,
        "spatial_grammar": selected_grammar,
        "available_grammars": sorted(SPATIAL_GRAMMARS),
        "layout_seed": _digest({"project": str(root), "grammar": selected_grammar})[:16],
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "layout_hints": build_layout_hints(selected_grammar, focus_scope.level.value, nodes),
        "lod_summary": build_lod_summary(nodes),
        "timeline": base.get("timeline", []),
        "activities": project_activities(dashboard),
        "delta": {},
        "motion_events": [],
        "legend": base.get("legend", []),
        "accessibility_summary": _accessibility_summary(focus_scope.as_dict(), nodes, edges),
    }
    projection["delta"] = projection_delta(None, projection)
    return projection


def build_narrative_node_detail_v4(
    config: dict[str, Any],
    project_root: Path,
    node_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    projection = build_narrative_projection_v4(config, project_root, **kwargs)
    selected = next((item for item in projection["nodes"] if item["node_id"] == node_id), None)
    if selected is None:
        raise KeyError(node_id)
    relationships = [
        item for item in projection["edges"]
        if item["source"] == node_id or item["target"] == node_id
    ]
    return {
        "ok": True,
        "schema": NODE_DETAIL_SCHEMA,
        "project_root": projection["project_root"],
        "projection_revision": projection["revision"],
        "node": selected,
        "relationships": relationships,
        "available_actions": selected.get("available_actions", []),
        "workspace_hints": selected.get("workspace_hints", {}),
    }


def spatial_projection_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    return projection_delta(previous, current)


def spatial_projection_motion_events(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    delta: dict[str, Any],
) -> list[dict[str, str]]:
    return projection_motion_events(previous, current, delta)


def _resolve_focus(
    level: NarrativeFocusLevel,
    focus: str,
    inventory: ProjectionInventory,
    dashboard: dict[str, Any],
) -> str:
    normalized = str(focus or "").strip()
    if level is NarrativeFocusLevel.CHARACTER:
        return normalized.removeprefix("character:")
    if level is NarrativeFocusLevel.BOOK:
        return "book"
    return resolve_focus(level.value, normalized, inventory.scenes, dashboard)


def _normalize_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique_nodes = dedupe_nodes(nodes)
    node_ids = {str(item.get("node_id") or "") for item in unique_nodes}
    unique_edges = [
        item for item in dedupe_edges(edges)
        if str(item.get("source") or "") in node_ids and str(item.get("target") or "") in node_ids
    ]
    return unique_nodes, unique_edges


def _project_title(root: Path, config: dict[str, Any]) -> str:
    configured = config.get("project_title") if isinstance(config, dict) else ""
    return str(configured or root.name).strip()


def _accessibility_summary(
    focus_scope: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> str:
    level = str(focus_scope.get("level") or "book")
    label = {"book": "全书", "chapter": "章节", "scene": "场景", "character": "人物"}.get(level, "作品")
    return f"{label}焦点下保留完整创作星链；共 {len(nodes)} 个可交互节点、{len(edges)} 条作品关系。"


def _digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


__all__ = [
    "NODE_DETAIL_SCHEMA",
    "PROJECTION_SCHEMA",
    "build_narrative_node_detail_v4",
    "build_narrative_projection_v4",
    "spatial_projection_delta",
    "spatial_projection_motion_events",
]
