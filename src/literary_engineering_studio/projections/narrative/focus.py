"""Pure focus-scope resolution over an immutable narrative projection."""

from __future__ import annotations

from typing import Any, Iterable

from .contracts import NarrativeFocusLevel, NarrativeFocusScope


def resolve_narrative_focus_scope(
    level: object,
    focus: object,
    nodes: object,
    edges: object,
) -> NarrativeFocusScope:
    clean_nodes = [item for item in nodes if isinstance(item, dict)] if isinstance(nodes, list) else []
    clean_edges = [item for item in edges if isinstance(item, dict)] if isinstance(edges, list) else []
    selected_level = NarrativeFocusLevel.parse(level)
    focus_id = _strip_entity_prefix(str(focus or "").strip(), selected_level)
    if selected_level is NarrativeFocusLevel.CHAPTER:
        return _chapter_scope(focus_id, clean_nodes, clean_edges)
    if selected_level is NarrativeFocusLevel.SCENE:
        return _scene_scope(focus_id, clean_nodes, clean_edges)
    if selected_level is NarrativeFocusLevel.CHARACTER:
        return _character_scope(focus_id, clean_nodes, clean_edges)
    return _book_scope(clean_nodes)


def _book_scope(nodes: list[dict[str, Any]]) -> NarrativeFocusScope:
    chapter_nodes = _nodes_of_type(nodes, "chapter")
    scene_nodes = _nodes_of_type(nodes, "scene")
    anchors = _node_ids(chapter_nodes or scene_nodes)
    return _scope(
        NarrativeFocusLevel.BOOK,
        "book",
        _chapter_ids(nodes),
        _entity_ids(scene_nodes),
        _entity_ids(_nodes_of_type(nodes, "character")),
        anchors,
        nodes,
    )


def _chapter_scope(
    focus_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> NarrativeFocusScope:
    chapter_id = focus_id or _first(_chapter_ids(nodes))
    scenes = [item for item in _nodes_of_type(nodes, "scene") if _scene_chapter(item) == chapter_id]
    chapter_nodes = [item for item in _nodes_of_type(nodes, "chapter") if _entity_id(item) == chapter_id]
    related = set(_node_ids(scenes + chapter_nodes))
    characters = _related_entities(nodes, edges, related, "character")
    return _scope(
        NarrativeFocusLevel.CHAPTER,
        chapter_id,
        (chapter_id,) if chapter_id else (),
        _entity_ids(scenes),
        characters,
        _node_ids(chapter_nodes + scenes),
        nodes,
    )


def _scene_scope(
    focus_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> NarrativeFocusScope:
    scenes = _nodes_of_type(nodes, "scene")
    scene_id = focus_id or _first(_entity_ids(scenes))
    selected = next((item for item in scenes if _entity_id(item) == scene_id), None)
    chapter_id = _scene_chapter(selected or {})
    neighbours = _adjacent_scenes(scenes, scene_id, chapter_id)
    selected_ids = {f"scene:{scene_id}"} if scene_id else set()
    characters = _related_entities(nodes, edges, selected_ids, "character")
    anchors = _node_ids([item for item in _nodes_of_type(nodes, "chapter") if _entity_id(item) == chapter_id])
    anchors += (f"scene:{scene_id}",) if scene_id else ()
    return _scope(
        NarrativeFocusLevel.SCENE,
        scene_id,
        (chapter_id,) if chapter_id else (),
        _entity_ids(neighbours),
        characters,
        anchors,
        nodes,
    )


def _character_scope(
    focus_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> NarrativeFocusScope:
    characters = _nodes_of_type(nodes, "character")
    character_id = focus_id or _first(_entity_ids(characters))
    node_id = f"character:{character_id}" if character_id else ""
    neighbours = _edge_neighbours(edges, node_id)
    scenes = [item for item in _nodes_of_type(nodes, "scene") if _node_id(item) in neighbours]
    chapters = {
        _entity_id(item)
        for item in _nodes_of_type(nodes, "chapter")
        if _node_id(item) in neighbours
    }
    chapters.update(_scene_chapter(item) for item in scenes if _scene_chapter(item))
    return _scope(
        NarrativeFocusLevel.CHARACTER,
        character_id,
        tuple(sorted(chapters)),
        _entity_ids(scenes),
        (character_id,) if character_id else (),
        (node_id,) if node_id and any(_node_id(item) == node_id for item in characters) else (),
        nodes,
    )


def _scope(
    level: NarrativeFocusLevel,
    focus_id: str,
    chapter_ids: Iterable[str],
    scene_ids: Iterable[str],
    character_ids: Iterable[str],
    anchors: Iterable[str],
    nodes: list[dict[str, Any]],
) -> NarrativeFocusScope:
    anchor_ids = _unique(anchors)
    anchor_set = set(anchor_ids)
    return NarrativeFocusScope(
        level=level,
        focus_id=focus_id,
        chapter_ids=_unique(chapter_ids),
        scene_ids=_unique(scene_ids),
        character_ids=_unique(character_ids),
        anchor_node_ids=anchor_ids,
        context_node_ids=tuple(node_id for node_id in _node_ids(nodes) if node_id not in anchor_set),
    )


def _adjacent_scenes(
    scenes: list[dict[str, Any]],
    scene_id: str,
    chapter_id: str,
) -> list[dict[str, Any]]:
    chapter_scenes = sorted(
        (item for item in scenes if _scene_chapter(item) == chapter_id),
        key=lambda item: (int(item.get("order") or 0), _node_id(item)),
    )
    index = next((position for position, item in enumerate(chapter_scenes) if _entity_id(item) == scene_id), -1)
    if index < 0:
        return []
    return chapter_scenes[max(0, index - 1) : min(len(chapter_scenes), index + 2)]


def _related_entities(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    target_ids: set[str],
    entity_type: str,
) -> tuple[str, ...]:
    related = {
        endpoint
        for edge in edges
        for endpoint in (str(edge.get("source") or ""), str(edge.get("target") or ""))
        if ({str(edge.get("source") or ""), str(edge.get("target") or "")} & target_ids)
    }
    return _entity_ids([item for item in _nodes_of_type(nodes, entity_type) if _node_id(item) in related])


def _edge_neighbours(edges: list[dict[str, Any]], node_id: str) -> set[str]:
    neighbours: set[str] = set()
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source == node_id and target:
            neighbours.add(target)
        if target == node_id and source:
            neighbours.add(source)
    return neighbours


def _chapter_ids(nodes: list[dict[str, Any]]) -> tuple[str, ...]:
    values = [_entity_id(item) for item in _nodes_of_type(nodes, "chapter")]
    values.extend(_scene_chapter(item) for item in _nodes_of_type(nodes, "scene"))
    return _unique(values)


def _nodes_of_type(nodes: list[dict[str, Any]], node_type: str) -> list[dict[str, Any]]:
    return [item for item in nodes if str(item.get("type") or "") == node_type]


def _entity_ids(nodes: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return _unique(_entity_id(item) for item in nodes)


def _node_ids(nodes: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return _unique(_node_id(item) for item in nodes)


def _entity_id(node: dict[str, Any]) -> str:
    return _node_id(node).partition(":")[2]


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("node_id") or "").strip()


def _scene_chapter(node: dict[str, Any]) -> str:
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    return str(metrics.get("chapter_id") or "").strip()


def _strip_entity_prefix(value: str, level: NarrativeFocusLevel) -> str:
    prefix = f"{level.value}:"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _first(values: Iterable[str]) -> str:
    return next(iter(values), "")
