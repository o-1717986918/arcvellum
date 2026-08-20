"""Lightweight graph projection for long-form audit evidence."""

from __future__ import annotations

from datetime import datetime, timezone

from .longform_issue_analysis import foreshadow_status
from .longform_models import LongformSceneRecord


def build_graph(
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    seen_nodes: set[str] = set()
    character_lookup = _character_nodes(characters, nodes, seen_nodes)
    _scene_nodes(scenes, character_lookup, nodes, edges, seen_nodes)
    _sequence_edges(scenes, edges)
    _foreshadowing_nodes(foreshadowing, nodes, edges, seen_nodes)
    return {
        "schema": "literary-engineering-workbench/longform-graph/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
    }


def _character_nodes(
    characters: list[dict[str, str]],
    nodes: list[dict[str, object]],
    seen: set[str],
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for character in characters:
        node_id = "character:" + (character["character_id"] or character["name"])
        _add_node(nodes, seen, node_id, "character", name=character["name"], role=character["role"], path=character["path"])
        if character["character_id"]:
            lookup[character["character_id"]] = node_id
        if character["name"]:
            lookup[character["name"]] = node_id
    return lookup


def _scene_nodes(
    scenes: list[LongformSceneRecord],
    character_lookup: dict[str, str],
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
) -> None:
    for scene in scenes:
        scene_node = "scene:" + scene.scene_id
        _add_node(nodes, seen, scene_node, "scene", chapter_id=scene.chapter_id, status=scene.status, path=scene.scene_path)
        if scene.location:
            location_node = "location:" + scene.location
            _add_node(nodes, seen, location_node, "location", name=scene.location)
            _add_edge(edges, scene_node, location_node, "located_at")
        for participant in scene.participants:
            character_node = character_lookup.get(participant, "character:" + participant)
            if participant not in character_lookup:
                _add_node(nodes, seen, character_node, "character_ref", name=participant)
            _add_edge(edges, character_node, scene_node, "appears_in")


def _sequence_edges(scenes: list[LongformSceneRecord], edges: list[dict[str, object]]) -> None:
    for previous, current in zip(scenes, scenes[1:]):
        _add_edge(edges, "scene:" + previous.scene_id, "scene:" + current.scene_id, "next_scene")


def _foreshadowing_nodes(
    rows: list[dict[str, str]],
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
) -> None:
    for row in rows:
        foreshadow_id = row.get("foreshadow_id") or row.get("id") or ""
        if not foreshadow_id:
            continue
        node = "foreshadow:" + foreshadow_id
        _add_node(nodes, seen, node, "foreshadowing", status=foreshadow_status(row), visibility=row.get("visibility", ""))
        setup = row.get("setup_scene") or ""
        payoff = row.get("actual_payoff_scene") or row.get("payoff_scene") or ""
        if setup:
            _add_edge(edges, "scene:" + setup, node, "sets_up")
        if payoff:
            _add_edge(edges, node, "scene:" + payoff, "pays_off_at")


def _add_node(
    nodes: list[dict[str, object]],
    seen: set[str],
    node_id: str,
    node_type: str,
    **attrs: object,
) -> None:
    if node_id not in seen:
        seen.add(node_id)
        nodes.append({"id": node_id, "type": node_type, **attrs})


def _add_edge(
    edges: list[dict[str, object]],
    source: str,
    target: str,
    relation: str,
    **attrs: object,
) -> None:
    edges.append({"source": source, "target": target, "relation": relation, **attrs})


__all__ = ["build_graph"]
