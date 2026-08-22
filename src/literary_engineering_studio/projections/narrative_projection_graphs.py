"""Book, chapter and scene graph builders for the v2 narrative projection."""

from __future__ import annotations

import re
from typing import Any

from .narrative_projection_evidence import append_scene_evidence, append_task_projection
from .narrative_projection_models import ProjectionInventory
from .narrative_projection_primitives import (
    chapter_label,
    edge,
    fact,
    formal_chars_by_chapter,
    formal_coverage,
    integer,
    node,
    order,
    scene_chapter,
)


def book_graph(
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    dashboard: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chapters = _group_scenes(inventory.scenes)
    ordered = sorted(chapters, key=order)
    coverage = formal_coverage(reader)
    formal_chars = formal_chars_by_chapter(reader)
    active_targets = _active_targets(dashboard)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for index, chapter in enumerate(ordered):
        _append_chapter(nodes, edges, chapter, chapters[chapter], ordered, index, coverage, formal_chars, active_targets)
    _append_book_characters(nodes, edges, inventory.characters, chapters)
    append_task_projection(nodes, edges, dashboard, inventory.scenes, level="book")
    return nodes, edges


def chapter_graph(
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    dashboard: dict[str, Any],
    chapter_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(inventory.scenes, key=lambda item: order(str(item.get("id") or "")))
    selected = [scene for scene in ordered if scene_chapter(scene) == chapter_id]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    _append_scene_chain(nodes, edges, ordered, formal_coverage(reader), {str(item.get("id") or "") for item in selected}, single_current=True)
    _append_characters(nodes, edges, inventory.characters, selected, subtitle_key="subtitle", edge_label="参与")
    _append_evidence(nodes, edges, selected, inventory)
    append_task_projection(nodes, edges, dashboard, ordered, level="chapter")
    return nodes, edges


def scene_graph(
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    dashboard: dict[str, Any],
    scene_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(inventory.scenes, key=lambda item: order(str(item.get("id") or "")))
    scene = next((item for item in ordered if str(item.get("id")) == scene_id), None)
    if scene is None:
        return [], []
    focused = [item for item in ordered if scene_chapter(item) == scene_chapter(scene)]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    _append_scene_chain(nodes, edges, ordered, formal_coverage(reader), {scene_id}, single_current=False)
    _append_characters(nodes, edges, inventory.characters, focused, subtitle_key="excerpt", edge_label="参与本场")
    _append_evidence(nodes, edges, focused, inventory)
    append_task_projection(nodes, edges, dashboard, [scene], level="scene")
    return nodes, edges


def constellation_graph(
    inventory: ProjectionInventory,
    reader: dict[str, Any],
    dashboard: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build the complete literary graph without projecting mechanical task files."""

    grouped = _group_scenes(inventory.scenes)
    ordered_chapters = sorted(grouped, key=order)
    ordered_scenes = sorted(inventory.scenes, key=lambda item: order(str(item.get("id") or "")))
    coverage = formal_coverage(reader)
    formal_chars = formal_chars_by_chapter(reader)
    active_targets = _active_targets(dashboard)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for index, chapter_id in enumerate(ordered_chapters):
        _append_chapter(
            nodes,
            edges,
            chapter_id,
            grouped[chapter_id],
            ordered_chapters,
            index,
            coverage,
            formal_chars,
            active_targets,
        )
    _append_scene_chain(
        nodes,
        edges,
        ordered_scenes,
        coverage,
        active_targets,
        single_current=False,
    )
    for scene in ordered_scenes:
        scene_id = str(scene.get("id") or "")
        chapter_id = scene_chapter(scene)
        if scene_id and chapter_id:
            edges.append(edge(f"chapter:{chapter_id}", f"scene:{scene_id}", "contains", "章节包含场景"))
    for scene in ordered_scenes:
        append_scene_evidence(
            nodes,
            edges,
            scene,
            inventory,
            include_pending=str(scene.get("id") or "") in active_targets,
        )
    return nodes, edges


def _append_chapter(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    chapter: str,
    scenes: list[dict[str, Any]],
    ordered: list[str],
    index: int,
    coverage: set[str],
    formal_chars: dict[str, int],
    active_targets: set[str],
) -> None:
    promoted = sum(1 for scene in scenes if str(scene.get("id")) in coverage)
    target = sum(integer(fact(scene, "目标字数")) for scene in scenes)
    actual = formal_chars.get(chapter, 0)
    status = _chapter_status(scenes, promoted, active_targets)
    nodes.append(node(
        f"chapter:{chapter}", "chapter", chapter_label(chapter), status,
        "scene-catalog", chapter, "overview", subtitle=f"{len(scenes)} 场 · 正文 {actual:,} 字",
        metrics={
            "scene_count": len(scenes), "promoted_count": promoted, "word_target": target,
            "formal_chars": actual, "entry_scene_id": str(scenes[0].get("id", "")),
        },
        order=index,
    ))
    if index:
        edges.append(edge(f"chapter:{ordered[index - 1]}", f"chapter:{chapter}", "sequence", "章节推进"))


def _chapter_status(scenes: list[dict[str, Any]], promoted: int, active_targets: set[str]) -> str:
    if promoted == len(scenes) and promoted:
        return "formal"
    if any(str(scene.get("status") or "").lower() in {"blocked", "failed", "conflict"} for scene in scenes):
        return "blocked"
    if promoted > 0 or any(str(scene.get("id") or "") in active_targets for scene in scenes):
        return "current"
    return "planned"


def _append_book_characters(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    chapters: dict[str, list[dict[str, Any]]],
) -> None:
    major = [item for item in characters if str(item.get("status")) == "major"][:12]
    for character in major:
        character_id = str(character.get("id") or "")
        title = str(character.get("title") or character_id)
        nodes.append(node(
            f"character:{character_id}", "character", title, "memory", "character",
            str(character.get("path") or character_id), "library", subtitle=str(character.get("subtitle") or "主要人物"),
        ))
        for chapter, chapter_scenes in chapters.items():
            if any(title in fact(scene, "参与者") for scene in chapter_scenes):
                edges.append(edge(f"character:{character_id}", f"chapter:{chapter}", "participates", "人物弧进入章节"))


def _append_scene_chain(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    coverage: set[str],
    current_ids: set[str],
    *,
    single_current: bool,
) -> None:
    current_taken = False
    for index, scene in enumerate(scenes):
        scene_id = str(scene.get("id") or "")
        status = _scene_status(scene, scene_id, coverage, current_ids, current_taken)
        current_taken = current_taken or (single_current and status == "current")
        nodes.append(_scene_node(scene, scene_id, status, index))
        if index:
            previous_id = str(scenes[index - 1].get("id"))
            edges.append(edge(f"scene:{previous_id}", f"scene:{scene_id}", "bridge", "场景承接"))


def _scene_status(
    scene: dict[str, Any],
    scene_id: str,
    coverage: set[str],
    current_ids: set[str],
    current_taken: bool,
) -> str:
    if scene_id in coverage:
        return "formal"
    if str(scene.get("status")) == "blocked":
        return "blocked"
    return "current" if scene_id in current_ids and not current_taken else "planned"


def _scene_node(scene: dict[str, Any], scene_id: str, status: str, index: int) -> dict[str, Any]:
    return node(
        f"scene:{scene_id}", "scene", str(scene.get("title") or scene_id), status,
        "scene", str(scene.get("path") or scene_id), "library", subtitle=str(scene.get("excerpt") or "")[:90],
        metrics={"word_target": integer(fact(scene, "目标字数")), "chapter_id": scene_chapter(scene)}, order=index,
    )


def _append_characters(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    *,
    subtitle_key: str,
    edge_label: str,
) -> None:
    participants = _participants(scenes)
    for character in characters:
        title = str(character.get("title") or "")
        if title not in participants:
            continue
        character_id = str(character.get("id") or "")
        subtitle = str(character.get(subtitle_key) or "")
        if subtitle_key == "excerpt":
            subtitle = subtitle[:90]
        nodes.append(node(
            f"character:{character_id}", "character", title or character_id, "memory", "character",
            str(character.get("path") or character_id), "library", subtitle=subtitle,
        ))
        for scene in scenes:
            if title in fact(scene, "参与者"):
                edges.append(edge(f"character:{character_id}", f"scene:{scene.get('id')}", "participates", edge_label))


def _append_evidence(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    inventory: ProjectionInventory,
    *,
    include_pending: bool = True,
) -> None:
    for scene in scenes:
        append_scene_evidence(nodes, edges, scene, inventory, include_pending=include_pending)


def _group_scenes(scenes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    chapters: dict[str, list[dict[str, Any]]] = {}
    for scene in scenes:
        chapters.setdefault(scene_chapter(scene), []).append(scene)
    return chapters


def _participants(scenes: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for scene in scenes:
        names.update(item.strip() for item in re.split(r"[、,，]", fact(scene, "参与者")) if item.strip())
    return names


def _active_targets(dashboard: dict[str, Any]) -> set[str]:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    return {str(item.get("target") or "") for item in actions if isinstance(item, dict)}


__all__ = ["book_graph", "chapter_graph", "constellation_graph", "scene_graph"]
