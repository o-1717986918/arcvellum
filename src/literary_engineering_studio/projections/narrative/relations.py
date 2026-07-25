"""Stable relation semantics for narrative projection and rendering."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import (
    NarrativeFocusLevel,
    NarrativeFocusScope,
    RelationFamily,
    RelationFocusState,
    RelationLodMode,
    RelationVisibilityProfile,
)
from .focus import resolve_narrative_focus_scope


_LABELS = {
    RelationFamily.NARRATIVE_SPINE: "叙事主脉",
    RelationFamily.CHAPTER_SCENE: "章节与场景",
    RelationFamily.SCENE_BRANCH: "场景分支",
    RelationFamily.SCENE_REVIEW: "审查证据",
    RelationFamily.SCENE_READER_QUESTION: "读者问题",
    RelationFamily.SCENE_PROMISE_PAYOFF: "承诺与兑现",
    RelationFamily.CHARACTER_SCENE: "人物轨迹",
    RelationFamily.EVIDENCE_CLAIM: "证据与主张",
    RelationFamily.CANON_STATE_IMPACT: "设定与状态影响",
    RelationFamily.WORKFLOW_CONTROL: "创作推进",
    RelationFamily.CONTEXT_ASSOCIATION: "上下文关联",
}

_WEIGHTS = {
    RelationFamily.NARRATIVE_SPINE: (1.0, 1.0, "chapter-centroid"),
    RelationFamily.CHAPTER_SCENE: (0.88, 1.0, "chapter-centroid"),
    RelationFamily.SCENE_BRANCH: (0.86, 1.0, "chapter-centroid"),
    RelationFamily.SCENE_REVIEW: (0.66, 0.94, "chapter-centroid"),
    RelationFamily.SCENE_READER_QUESTION: (0.62, 0.94, "chapter-centroid"),
    RelationFamily.SCENE_PROMISE_PAYOFF: (0.68, 1.0, "chapter-centroid"),
    RelationFamily.CHARACTER_SCENE: (0.62, 1.0, "character-chapter-centroid"),
    RelationFamily.EVIDENCE_CLAIM: (0.58, 0.9, "claim-centroid"),
    RelationFamily.CANON_STATE_IMPACT: (0.7, 1.0, "chapter-centroid"),
    RelationFamily.WORKFLOW_CONTROL: (0.92, 1.0, "active-task"),
    RelationFamily.CONTEXT_ASSOCIATION: (0.48, 0.78, "chapter-centroid"),
}


def build_focused_relations(
    items: object,
    nodes: list[dict[str, Any]],
    level: object,
    focus: object,
) -> tuple[list[dict[str, Any]], NarrativeFocusScope, list[dict[str, Any]]]:
    normalized = normalize_relation_edges(items, nodes)
    scope = resolve_narrative_focus_scope(level, focus, nodes, normalized)
    focused = apply_relation_focus(normalized, scope)
    profiles = [profile.as_dict() for profile in build_relation_profiles(focused)]
    return focused, scope, profiles


def normalize_relation_edges(items: object, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_ids = {str(node.get("node_id") or "") for node in nodes}
    nodes_by_id = {str(node.get("node_id") or ""): node for node in nodes}
    result: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        target = str(item.get("target") or "")
        if source not in node_ids or target not in node_ids:
            continue
        edge = dict(item)
        edge_type = str(edge.get("type") or "")
        edge["strength"] = _edge_strength(edge_type)
        edge["direction"] = "forward" if edge_type in {"sequence", "bridge", "raises", "promise", "workflow"} else "context"
        edge["temporal_relation"] = "advances" if edge_type in {"sequence", "bridge"} else "associates"
        edge["relation_family"] = _relation_family(edge_type, nodes_by_id.get(source), nodes_by_id.get(target)).value
        result.append(edge)
    return result


def apply_relation_focus(
    edges: list[dict[str, Any]],
    scope: NarrativeFocusScope,
) -> list[dict[str, Any]]:
    anchors = set(scope.anchor_node_ids)
    result: list[dict[str, Any]] = []
    for item in edges:
        edge = dict(item)
        edge["focus_state"] = _focus_state(edge, scope.level, anchors).value
        result.append(edge)
    return result


def build_relation_profiles(edges: list[dict[str, Any]]) -> list[RelationVisibilityProfile]:
    counts = Counter(str(edge.get("relation_family") or "") for edge in edges)
    focused = Counter(
        str(edge.get("relation_family") or "")
        for edge in edges
        if str(edge.get("focus_state") or "") in {
            RelationFocusState.INTERNAL.value,
            RelationFocusState.ATTACHED.value,
        }
    )
    return [_profile(family, counts[family.value], focused[family.value]) for family in RelationFamily]


def _profile(
    family: RelationFamily,
    edge_count: int,
    focused_edge_count: int,
) -> RelationVisibilityProfile:
    base_weight, focus_weight, anchor = _WEIGHTS[family]
    return RelationVisibilityProfile(
        family=family,
        label=_LABELS[family],
        edge_count=edge_count,
        focused_edge_count=focused_edge_count,
        far_mode=RelationLodMode.AGGREGATE,
        mid_mode=RelationLodMode.INDIVIDUAL,
        near_mode=RelationLodMode.EMPHASIZED,
        aggregate_anchor=anchor,
        base_weight=base_weight,
        focus_weight=focus_weight,
    )


def _relation_family(
    edge_type: str,
    source: dict[str, Any] | None,
    target: dict[str, Any] | None,
) -> RelationFamily:
    endpoint_types = {str((source or {}).get("type") or ""), str((target or {}).get("type") or "")}
    if endpoint_types == {"chapter", "scene"}:
        return RelationFamily.CHAPTER_SCENE
    mapping = {
        "sequence": RelationFamily.NARRATIVE_SPINE,
        "bridge": RelationFamily.NARRATIVE_SPINE,
        "branch": RelationFamily.SCENE_BRANCH,
        "review": RelationFamily.SCENE_REVIEW,
        "raises": RelationFamily.SCENE_READER_QUESTION,
        "promise": RelationFamily.SCENE_PROMISE_PAYOFF,
        "participates": RelationFamily.CHARACTER_SCENE,
        "canon": RelationFamily.CANON_STATE_IMPACT,
        "workflow": RelationFamily.WORKFLOW_CONTROL,
    }
    if edge_type in mapping:
        return mapping[edge_type]
    if endpoint_types & {"review", "canon"} and endpoint_types & {"promise", "reader-question"}:
        return RelationFamily.EVIDENCE_CLAIM
    return RelationFamily.CONTEXT_ASSOCIATION


def _focus_state(
    edge: dict[str, Any],
    level: NarrativeFocusLevel,
    anchors: set[str],
) -> RelationFocusState:
    if level is NarrativeFocusLevel.BOOK:
        return RelationFocusState.GLOBAL
    endpoints = {str(edge.get("source") or ""), str(edge.get("target") or "")}
    focused_count = len(endpoints & anchors)
    if focused_count == 2:
        return RelationFocusState.INTERNAL
    if focused_count == 1:
        return RelationFocusState.ATTACHED
    return RelationFocusState.CONTEXT


def _edge_strength(edge_type: str) -> float:
    return {
        "sequence": 1.0,
        "bridge": 0.96,
        "workflow": 0.92,
        "branch": 0.86,
        "canon": 0.7,
        "promise": 0.68,
        "review": 0.66,
        "participates": 0.62,
        "raises": 0.62,
    }.get(edge_type, 0.48)
