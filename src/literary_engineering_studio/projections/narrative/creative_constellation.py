"""Creative asset and interaction semantics for narrative projection v4."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from ..narrative_projection_primitives import dedupe_edges, dedupe_nodes, edge, node
from .contracts import (
    CreativeNodeKind,
    CreativeNodeLifecycle,
    NodeActionDescriptor,
    NodeActionKind,
)


_SECTION_KIND = {
    "drafts": CreativeNodeKind.DRAFT,
    "world": CreativeNodeKind.WORLD,
    "style": CreativeNodeKind.STYLE,
    "word_budget": CreativeNodeKind.WORD_BUDGET,
    "story_architecture": CreativeNodeKind.STORY_ARCHITECTURE,
    "decisions": CreativeNodeKind.HUMAN_DECISION,
}

_TYPE_KIND = {
    "chapter": CreativeNodeKind.CHAPTER,
    "scene": CreativeNodeKind.SCENE,
    "character": CreativeNodeKind.CHARACTER,
    "branch": CreativeNodeKind.BRANCH,
    "review": CreativeNodeKind.REVIEW,
    "canon": CreativeNodeKind.CANON,
    "promise": CreativeNodeKind.PROMISE,
    "reader-question": CreativeNodeKind.READER_QUESTION,
    "formal-prose": CreativeNodeKind.FORMAL_PROSE,
    "project": CreativeNodeKind.PROJECT,
}


def augment_creative_constellation(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    library: dict[str, Any],
    reader: dict[str, Any],
    project_root: Path,
    project_title: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add meaningful project assets while excluding mechanical receipt files."""

    result_nodes = [
        node(
            "project:origin",
            "project",
            project_title or project_root.name,
            "current",
            "project",
            "project.yaml",
            "overview",
            subtitle="作品的创作原点与全书脉络",
            order=-1,
        ),
        *(item for item in nodes if not _is_mechanical_node(item)),
    ]
    result_edges = list(edges)
    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    for section, kind in _SECTION_KIND.items():
        for index, item in enumerate(_rows(sections.get(section))):
            if _is_mechanical_receipt(item):
                continue
            asset_node = _asset_node(section, kind, item, index)
            result_nodes.append(asset_node)
            parent_id = _asset_parent(asset_node, item)
            result_edges.append(edge(parent_id, asset_node["node_id"], "contains", _edge_label(kind)))
    _append_reader_units(result_nodes, result_edges, reader)
    for item in list(result_nodes):
        node_id = str(item.get("node_id") or "")
        if node_id.startswith("chapter:"):
            result_edges.append(edge("project:origin", node_id, "contains", "作品包含章节"))
        elif node_id.startswith("character:"):
            result_edges.append(edge("project:origin", node_id, "contains", "作品人物"))
    return dedupe_nodes(result_nodes), dedupe_edges(result_edges)


def enrich_creative_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parents = _semantic_parents(nodes, edges)
    result: list[dict[str, Any]] = []
    for item in nodes:
        enriched = dict(item)
        kind = _node_kind(enriched)
        lifecycle = _lifecycle(enriched, kind)
        node_id = str(enriched.get("node_id") or "")
        parent_id = parents.get(node_id)
        enriched.update(
            {
                "creative_kind": kind.value,
                "lifecycle": lifecycle.value,
                "parent_id": parent_id,
                "hierarchy_depth": _hierarchy_depth(node_id, parent_id, kind),
                "depth_role": _depth_role(kind),
                "available_actions": [
                    action.as_dict()
                    for action in _available_actions(enriched, kind, lifecycle)
                ],
                "workspace_hints": _workspace_hints(kind),
            }
        )
        result.append(enriched)
    return result


def project_activities(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    current = dashboard.get("current_task") if isinstance(dashboard.get("current_task"), dict) else {}
    current_route = str(current.get("route") or "")
    current_target = str(current.get("target") or current.get("scene_id") or "")
    return [
        {
            "activity_id": f"workflow:{index}:{item.get('route', 'auto')}:{item.get('target', '')}",
            "kind": "workflow",
            "status": (
                "active"
                if index == 0
                and current_route
                and current_route == str(item.get("route") or "")
                and (not current_target or current_target == str(item.get("target") or ""))
                else "available"
            ),
            "route": str(item.get("route") or "auto"),
            "target": str(item.get("target") or ""),
            "label": "下一项创作工作" if index == 0 else "后续创作工作",
            "summary": str(item.get("friendly_action") or item.get("next_action") or "").strip(),
        }
        for index, item in enumerate(actions)
        if isinstance(item, dict)
    ]


def _asset_node(
    section: str,
    kind: CreativeNodeKind,
    item: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    asset_id = str(item.get("id") or f"{section}-{index}")
    status = str(item.get("status") or "planned")
    return node(
        f"{kind.value}:{asset_id}",
        kind.value,
        str(item.get("title") or asset_id),
        status,
        section,
        str(item.get("path") or asset_id),
        _navigation(kind),
        subtitle=str(item.get("excerpt") or item.get("subtitle") or "")[:120],
        metrics={
            "section": section,
            "badges": list(item.get("badges") or []),
            "key_points": list(item.get("key_points") or [])[:6],
        },
        order=index,
    )


def _append_reader_units(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    reader: dict[str, Any],
) -> None:
    for index, unit in enumerate(_rows(reader.get("units"))):
        unit_id = str(unit.get("unit_id") or f"unit-{index}")
        chapter_id = str(unit.get("chapter_id") or "")
        scene_ids = [str(value) for value in unit.get("coverage", []) if str(value)]
        if not scene_ids and unit.get("scene_id"):
            scene_ids = [str(unit.get("scene_id"))]
        prose_id = f"formal-prose:{unit_id}"
        nodes.append(node(
            prose_id,
            "formal-prose",
            str(unit.get("title") or "正式正文"),
            "formal",
            "reader-unit",
            unit_id,
            "reader",
            subtitle=f"{int(unit.get('chinese_content_chars') or 0):,} 字 · 已进入正式长卷",
            metrics={
                "chapter_id": chapter_id,
                "scene_ids": scene_ids,
                "body_endpoint": str(unit.get("body_endpoint") or ""),
            },
            order=index,
        ))
        parent = f"scene:{scene_ids[0]}" if scene_ids else f"chapter:{chapter_id}" if chapter_id else "project:origin"
        edges.append(edge(parent, prose_id, "formal-prose", "晋升为正式正文"))


def _semantic_parents(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, str]:
    known = {str(item.get("node_id") or "") for item in nodes}
    parents: dict[str, str] = {}
    for item in nodes:
        node_id = str(item.get("node_id") or "")
        node_type = str(item.get("type") or "")
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        if node_type == "scene" and metrics.get("chapter_id"):
            parents[node_id] = f"chapter:{metrics['chapter_id']}"
        elif node_type in {"chapter", "character", "world", "style", "story-architecture", "word-budget", "human-decision"}:
            parents[node_id] = "project:origin"
    priority = {
        "contains": 0,
        "branch": 1,
        "review": 1,
        "canon": 1,
        "raises": 1,
        "promise": 1,
        "formal-prose": 1,
        "participates": 4,
        "sequence": 6,
        "bridge": 6,
    }
    selected: dict[str, tuple[int, str]] = {}
    for relation in edges:
        source = str(relation.get("source") or "")
        target = str(relation.get("target") or "")
        if source not in known or target not in known or target in parents:
            continue
        weight = priority.get(str(relation.get("type") or ""), 5)
        if target not in selected or weight < selected[target][0]:
            selected[target] = (weight, source)
    parents.update({target: source for target, (_weight, source) in selected.items()})
    return parents


def _node_kind(item: dict[str, Any]) -> CreativeNodeKind:
    node_type = str(item.get("type") or "")
    if node_type == "world":
        source = str(item.get("source_id") or "").lower()
        if "location" in source:
            return CreativeNodeKind.LOCATION
        if "organization" in source:
            return CreativeNodeKind.ORGANIZATION
    if node_type in _TYPE_KIND:
        return _TYPE_KIND[node_type]
    try:
        return CreativeNodeKind(node_type)
    except ValueError:
        return CreativeNodeKind.EVENT


def _lifecycle(item: dict[str, Any], kind: CreativeNodeKind) -> CreativeNodeLifecycle:
    status = str(item.get("status") or "").strip().lower()
    if status in {"blocked", "failed", "conflict"}:
        return CreativeNodeLifecycle.BLOCKED
    if status in {"needs_revision", "revise", "pass_with_notes"}:
        return CreativeNodeLifecycle.REVISION
    if status in {"waiting_human", "pending_approval", "awaiting"}:
        return CreativeNodeLifecycle.AWAITING
    if status in {"current", "running", "active", "queued"}:
        return CreativeNodeLifecycle.ACTIVE
    if status in {"reviewing", "under_review"}:
        return CreativeNodeLifecycle.REVIEWING
    if status in {"formal", "pass", "ready", "promoted", "approved", "complete", "completed", "selected"}:
        return CreativeNodeLifecycle.FORMAL
    if status in {"superseded", "rejected"}:
        return CreativeNodeLifecycle.SUPERSEDED
    if status in {"delivered", "released"}:
        return CreativeNodeLifecycle.DELIVERED
    if kind in {CreativeNodeKind.BRANCH, CreativeNodeKind.REVIEW} and status in {"alternative", "planned"}:
        return CreativeNodeLifecycle.AVAILABLE
    return CreativeNodeLifecycle.LATENT if status in {"", "latent"} else CreativeNodeLifecycle.AVAILABLE


def _available_actions(
    item: dict[str, Any],
    kind: CreativeNodeKind,
    lifecycle: CreativeNodeLifecycle,
) -> list[NodeActionDescriptor]:
    node_id = str(item.get("node_id") or "")
    actions = [
        NodeActionDescriptor(f"inspect:{node_id}", NodeActionKind.INSPECT, "查看详情", node_id),
        NodeActionDescriptor(f"focus:{node_id}", NodeActionKind.FOCUS, "聚焦星链", node_id),
    ]
    workspace = _workspace_hints(kind)["preferred_workspace"]
    if workspace:
        actions.append(NodeActionDescriptor(
            f"workspace:{node_id}",
            NodeActionKind.OPEN_WORKSPACE,
            _workspace_label(kind),
            node_id,
            workspace=workspace,
        ))
    if kind in {CreativeNodeKind.CHAPTER, CreativeNodeKind.SCENE} and lifecycle is not CreativeNodeLifecycle.FORMAL:
        actions.append(NodeActionDescriptor(
            f"advance:{node_id}",
            NodeActionKind.RUN_CREATIVE_STEP,
            "继续创作",
            node_id,
            mutates_project=True,
            risk_level="draft",
        ))
    if kind is CreativeNodeKind.BRANCH and lifecycle in {CreativeNodeLifecycle.AVAILABLE, CreativeNodeLifecycle.AWAITING}:
        actions.append(NodeActionDescriptor(
            f"choose:{node_id}",
            NodeActionKind.CHOOSE_BRANCH,
            "选择这条分支",
            node_id,
            mutates_project=True,
            requires_confirmation=True,
            risk_level="formal",
        ))
    if kind is CreativeNodeKind.REVIEW and lifecycle in {CreativeNodeLifecycle.BLOCKED, CreativeNodeLifecycle.REVISION}:
        actions.append(NodeActionDescriptor(
            f"revise:{node_id}",
            NodeActionKind.REQUEST_REVISION,
            "按审查意见修订",
            node_id,
            mutates_project=True,
            risk_level="draft",
        ))
    if kind is CreativeNodeKind.HUMAN_DECISION and lifecycle is not CreativeNodeLifecycle.FORMAL:
        actions.append(NodeActionDescriptor(
            f"approve:{node_id}",
            NodeActionKind.APPROVE,
            "作出决定",
            node_id,
            mutates_project=True,
            requires_confirmation=True,
            risk_level="formal",
        ))
    return actions


def _workspace_hints(kind: CreativeNodeKind) -> dict[str, Any]:
    preferred = {
        CreativeNodeKind.FORMAL_PROSE: "reader",
        CreativeNodeKind.DRAFT: "reader",
        CreativeNodeKind.CHARACTER: "archive",
        CreativeNodeKind.WORLD: "archive",
        CreativeNodeKind.LOCATION: "archive",
        CreativeNodeKind.ORGANIZATION: "archive",
        CreativeNodeKind.STYLE: "style",
        CreativeNodeKind.REVIEW: "quality",
        CreativeNodeKind.REVISION: "quality",
        CreativeNodeKind.HUMAN_DECISION: "decisions",
        CreativeNodeKind.WORD_BUDGET: "rules",
        CreativeNodeKind.STORY_ARCHITECTURE: "strategy",
    }.get(kind, "node-detail")
    return {
        "preferred_workspace": preferred,
        "supports_float": True,
        "supports_dock": preferred != "node-detail",
        "supports_fullscreen": preferred in {"reader", "archive", "style", "quality", "strategy"},
    }


def _hierarchy_depth(node_id: str, parent_id: str | None, kind: CreativeNodeKind) -> int:
    if kind is CreativeNodeKind.PROJECT:
        return 0
    if kind in {CreativeNodeKind.CHAPTER, CreativeNodeKind.CHARACTER, CreativeNodeKind.WORLD, CreativeNodeKind.STYLE, CreativeNodeKind.STORY_ARCHITECTURE, CreativeNodeKind.WORD_BUDGET}:
        return 1
    if kind is CreativeNodeKind.SCENE:
        return 2
    if parent_id and parent_id.startswith("scene:"):
        return 3
    return 2


def _depth_role(kind: CreativeNodeKind) -> str:
    if kind in {CreativeNodeKind.PROJECT, CreativeNodeKind.STORY_ARCHITECTURE, CreativeNodeKind.WORD_BUDGET}:
        return "far-anchor"
    if kind in {CreativeNodeKind.CHAPTER, CreativeNodeKind.CHARACTER, CreativeNodeKind.WORLD, CreativeNodeKind.STYLE}:
        return "mid-structure"
    return "near-detail"


def _asset_parent(asset_node: dict[str, Any], item: dict[str, Any]) -> str:
    scene_id = _scene_reference(item)
    return f"scene:{scene_id}" if scene_id else "project:origin"


def _scene_reference(item: dict[str, Any]) -> str:
    haystack = " ".join(str(item.get(key) or "") for key in ("id", "path", "subtitle"))
    match = re.search(r"scene[_-]?\d+", haystack, flags=re.IGNORECASE)
    return match.group(0).replace("-", "_").lower() if match else ""


def _is_mechanical_receipt(item: dict[str, Any]) -> bool:
    path = str(item.get("path") or "").lower()
    return any(token in path for token in ("agent_completion", ".agent_tasks", "task.json", "receipt"))


def _is_mechanical_node(item: dict[str, Any]) -> bool:
    """Keep workflow evidence out of the literary graph even when v3 saw it."""

    identity = " ".join(
        str(item.get(key) or "").lower()
        for key in ("node_id", "source_id", "source_type", "label")
    )
    return any(token in identity for token in (
        ".agent_tasks",
        "_agent_tasks_",
        "agent_completion",
        "task.json",
        "completion marker",
        "平台 agent 任务说明",
    ))


def _rows(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _navigation(kind: CreativeNodeKind) -> str:
    if kind in {CreativeNodeKind.DRAFT, CreativeNodeKind.FORMAL_PROSE}:
        return "reader"
    if kind is CreativeNodeKind.STYLE:
        return "style"
    if kind is CreativeNodeKind.HUMAN_DECISION:
        return "decisions"
    return "library"


def _edge_label(kind: CreativeNodeKind) -> str:
    return {
        CreativeNodeKind.STORY_ARCHITECTURE: "全书结构",
        CreativeNodeKind.WORD_BUDGET: "长篇规模",
        CreativeNodeKind.STYLE: "文风约束",
        CreativeNodeKind.WORLD: "世界设定",
        CreativeNodeKind.DRAFT: "正文候选",
        CreativeNodeKind.HUMAN_DECISION: "创作决定",
    }.get(kind, "作品资产")


def _workspace_label(kind: CreativeNodeKind) -> str:
    return {
        CreativeNodeKind.FORMAL_PROSE: "打开正文长卷",
        CreativeNodeKind.DRAFT: "阅读候选正文",
        CreativeNodeKind.CHARACTER: "打开人物档案",
        CreativeNodeKind.WORLD: "打开世界档案",
        CreativeNodeKind.LOCATION: "打开地点档案",
        CreativeNodeKind.ORGANIZATION: "打开组织档案",
        CreativeNodeKind.STYLE: "打开文风工作台",
        CreativeNodeKind.REVIEW: "查看审查证据",
        CreativeNodeKind.HUMAN_DECISION: "打开决策台",
        CreativeNodeKind.WORD_BUDGET: "调整创作规则",
        CreativeNodeKind.STORY_ARCHITECTURE: "查看全书策略",
    }.get(kind, "打开工作台")


__all__ = ["augment_creative_constellation", "enrich_creative_nodes", "project_activities"]
