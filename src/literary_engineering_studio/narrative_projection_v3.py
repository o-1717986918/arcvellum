"""Spatial, rebuildable read model built on the formal v2 narrative evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.rhythm_plan import load_rhythm_plan

from . import narrative_projection as narrative_projection_v2
from .narrative_projection import build_narrative_projection, projection_delta, projection_motion_events


PROJECTION_SCHEMA = "arcvellum/narrative-projection/v3"
SPATIAL_GRAMMARS = {"spine", "braid", "strata", "constellation", "loop", "stage"}


def build_narrative_projection_v3(
    config: dict[str, Any],
    project_root: Path,
    *,
    level: str = "book",
    focus: str = "",
    grammar: str = "auto",
    dashboard_payload: dict[str, Any] | None = None,
    library_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decorate v2 formal evidence with stable spatial semantics.

    Coordinates deliberately stay out of this response. The client layout engine owns
    camera-space placement, while this model exposes only reproducible narrative facts.
    """

    base = build_narrative_projection(
        config,
        project_root,
        level=level,
        focus=focus,
        dashboard_payload=dashboard_payload,
        library_payload=library_payload,
    )
    selected_grammar = _resolve_grammar(grammar, base)
    rhythm_hints = _rhythm_hints(project_root)
    nodes = _spatial_nodes(base.get("nodes", []), base.get("edges", []), selected_grammar, rhythm_hints)
    edges = _spatial_edges(base.get("edges", []), nodes)
    clusters = _clusters(nodes)
    # Reuse the v2 read-model entry so cached deployments and test fixtures
    # observe exactly the same reader evidence as the base projection.
    reader_payload = narrative_projection_v2.build_reader_manifest(project_root)
    effective_dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else {}
    source_revisions = {
        "narrative_v2": str(base.get("revision") or ""),
        "dashboard": _digest(effective_dashboard),
        "library": _digest(library_payload or {}),
        "reader": _digest({
            "revision": reader_payload.get("revision"),
            "units": reader_payload.get("units"),
            "total_chinese_content_chars": reader_payload.get("total_chinese_content_chars"),
        }),
        "jobs": _digest({
            "current_task": effective_dashboard.get("current_task"),
            "next_actions": effective_dashboard.get("next_actions"),
            "active_run": effective_dashboard.get("active_run"),
        }),
        "rhythm": _digest(rhythm_hints),
    }
    revision = _digest(
        {
            "base": base.get("revision"),
            "grammar": selected_grammar,
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters,
            "source_revisions": source_revisions,
        }
    )
    summary = dict(base.get("summary") or {})
    summary.update(
        {
            "cluster_count": len(clusters),
            "spatial_grammar": selected_grammar,
            "interactive_node_count": sum(1 for node in nodes if node["detail_level"] != "far"),
        }
    )
    return {
        "ok": True,
        "schema": PROJECTION_SCHEMA,
        "project_root": str(project_root.resolve()),
        "generated_at": base.get("generated_at"),
        "revision": revision,
        "sequence": 0,
        "source_revisions": source_revisions,
        "level": base.get("level", "book"),
        "focus": base.get("focus", ""),
        "spatial_grammar": selected_grammar,
        "available_grammars": sorted(SPATIAL_GRAMMARS),
        "layout_seed": _digest({"project": str(project_root.resolve()), "grammar": selected_grammar})[:16],
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "layout_hints": _layout_hints(selected_grammar, base.get("level", "book"), nodes),
        "lod_summary": _lod_summary(nodes),
        "timeline": base.get("timeline", []),
        "delta": projection_delta(None, {"nodes": nodes, "edges": edges}),
        "motion_events": [],
        "legend": base.get("legend", []),
        "accessibility_summary": base.get("accessibility_summary", ""),
    }


def build_narrative_node_detail_v3(
    config: dict[str, Any],
    project_root: Path,
    node_id: str,
    *,
    level: str = "book",
    focus: str = "",
    grammar: str = "auto",
    dashboard_payload: dict[str, Any] | None = None,
    library_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    projection = build_narrative_projection_v3(
        config,
        project_root,
        level=level,
        focus=focus,
        grammar=grammar,
        dashboard_payload=dashboard_payload,
        library_payload=library_payload,
    )
    node = next((item for item in projection["nodes"] if item["node_id"] == node_id), None)
    if node is None:
        raise KeyError(node_id)
    relationships = [
        edge
        for edge in projection["edges"]
        if edge["source"] == node_id or edge["target"] == node_id
    ]
    return {
        "ok": True,
        "schema": "arcvellum/narrative-node-detail/v1",
        "project_root": projection["project_root"],
        "projection_revision": projection["revision"],
        "node": node,
        "relationships": relationships,
        "available_actions": _available_actions(node),
    }


def spatial_projection_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    return projection_delta(previous, current)


def spatial_projection_motion_events(previous: dict[str, Any] | None, current: dict[str, Any], delta: dict[str, Any]) -> list[dict[str, str]]:
    return projection_motion_events(previous, current, delta)


def _spatial_nodes(items: Any, edges: Any, grammar: str, rhythm_hints: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    raw_nodes = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    raw_edges = [item for item in edges if isinstance(item, dict)] if isinstance(edges, list) else []
    parent_map = _parent_map(raw_edges)
    primary_count = sum(1 for item in raw_nodes if item.get("type") in {"chapter", "scene"})
    result: list[dict[str, Any]] = []
    for index, item in enumerate(raw_nodes):
        node_id = str(item.get("node_id") or "")
        node_type = str(item.get("type") or "unknown")
        node = dict(item)
        node.update(
            {
                "parent_id": parent_map.get(node_id),
                "cluster_id": _cluster_id(node, grammar),
                "time_band": _time_band(node, primary_count),
                "importance": _importance(node),
                "detail_level": _detail_level(node, primary_count),
                "world_hint": _world_hint(node, grammar, index),
                "detail_endpoint": f"/narrative/projection/v3/nodes/{node_id}",
            }
        )
        hint = _rhythm_hint_for_node(node, rhythm_hints)
        if hint:
            node["rhythm"] = hint
        result.append(node)
    return result


def _rhythm_hints(project_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Build small projection hints from the formal rhythm plan.

    The spatial view never writes rhythm data or invents a second authority. It
    only summarizes the same scene contracts used by generation and review so
    a user-visible curve changes with the project's actual creative settings.
    """
    try:
        plan = load_rhythm_plan(project_root)
    except OSError:
        return {"scenes": {}, "chapters": {}}
    raw_entries = plan.get("entries") if isinstance(plan.get("entries"), list) else []
    scene_hints: dict[str, dict[str, Any]] = {}
    chapter_entries: dict[str, list[dict[str, Any]]] = {}
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "").strip()
        chapter_id = str(item.get("chapter_id") or "").strip()
        hint = _normalise_rhythm_hint(item)
        if scene_id:
            scene_hints[scene_id] = hint
        if chapter_id:
            chapter_entries.setdefault(chapter_id, []).append(hint)
    return {
        "scenes": scene_hints,
        "chapters": {chapter_id: _aggregate_rhythm_hints(items) for chapter_id, items in chapter_entries.items()},
    }


def _rhythm_hint_for_node(node: dict[str, Any], rhythm_hints: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    node_type = str(node.get("type") or "")
    if node_type == "chapter":
        return dict(rhythm_hints.get("chapters", {}).get(str(node.get("source_id") or ""), {}))
    if node_type == "scene":
        scene_id = str(node.get("node_id") or "").split(":", 1)[-1]
        return dict(rhythm_hints.get("scenes", {}).get(scene_id, {}))
    return {}


def _normalise_rhythm_hint(item: dict[str, Any]) -> dict[str, Any]:
    curve = item.get("tension_curve") if isinstance(item.get("tension_curve"), dict) else {}
    entry = _clamp_tension(curve.get("entry"), 2)
    peak = _clamp_tension(curve.get("peak"), 3)
    exit_value = _clamp_tension(curve.get("exit"), 2)
    return {
        "entry": entry,
        "peak": peak,
        "exit": exit_value,
        "pace": str(item.get("pace") or "balanced"),
        "role": str(item.get("rhythm_role") or "mixed"),
        "detail_level": str(item.get("detail_level") or "standard"),
        "weight": max(1, int(item.get("word_count_target") or 1)),
        "timeline_start": _positive_int(item.get("timeline_order")),
        "timeline_end": _positive_int(item.get("timeline_order")),
        "spatial_time_gap_before": _positive_float(item.get("spatial_time_gap_before")),
        "source": str(item.get("source") or "scene-contract"),
    }


def _aggregate_rhythm_hints(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {}
    weight = sum(max(1, int(item.get("weight") or 1)) for item in items)
    def weighted(field: str) -> int:
        return round(sum(int(item.get(field) or 0) * max(1, int(item.get("weight") or 1)) for item in items) / weight)
    lead = max(items, key=lambda item: (int(item.get("peak") or 0), int(item.get("weight") or 0), str(item.get("pace") or "")))
    return {
        "entry": weighted("entry"),
        "peak": weighted("peak"),
        "exit": weighted("exit"),
        "pace": str(lead.get("pace") or "balanced"),
        "role": str(lead.get("role") or "mixed"),
        "detail_level": _highest_detail_level(items),
        "weight": weight,
        "timeline_start": min((int(item.get("timeline_start") or 0) for item in items if int(item.get("timeline_start") or 0) > 0), default=0),
        "timeline_end": max((int(item.get("timeline_end") or 0) for item in items), default=0),
        "spatial_time_gap_before": next((float(item.get("spatial_time_gap_before") or 0) for item in items if float(item.get("spatial_time_gap_before") or 0) > 0), 0.0),
        "source": "chapter-rhythm-aggregate",
    }


def _highest_detail_level(items: list[dict[str, Any]]) -> str:
    order = {"summary": 0, "lean": 1, "standard": 2, "expanded": 3, "set_piece": 4}
    return max((str(item.get("detail_level") or "standard") for item in items), key=lambda value: order.get(value, 2))


def _clamp_tension(value: object, default: int) -> int:
    try:
        return min(5, max(1, int(value)))
    except (TypeError, ValueError):
        return default


def _positive_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _positive_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _spatial_edges(items: Any, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_ids = {node["node_id"] for node in nodes}
    result: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("source")) not in node_ids or str(item.get("target")) not in node_ids:
            continue
        edge = dict(item)
        edge["strength"] = _edge_strength(edge)
        edge["direction"] = "forward" if edge.get("type") in {"sequence", "bridge", "raises", "promise", "workflow"} else "context"
        edge["temporal_relation"] = "advances" if edge.get("type") in {"sequence", "bridge"} else "associates"
        result.append(edge)
    return result


def _clusters(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for node in nodes:
        grouped.setdefault(str(node["cluster_id"]), []).append(str(node["node_id"]))
    return [
        {
            "cluster_id": cluster_id,
            "label": _cluster_label(cluster_id),
            "node_ids": node_ids,
            "importance": round(max((_importance(next(node for node in nodes if node["node_id"] == node_id)) for node_id in node_ids), default=0.1), 3),
        }
        for cluster_id, node_ids in sorted(grouped.items())
    ]


def _layout_hints(grammar: str, level: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "grammar": grammar,
        "level": level,
        "primary_axis": "depth" if grammar in {"spine", "strata", "stage"} else "braid",
        "focus_bias": "lower-right" if grammar == "braid" else "center",
        "node_count": len(nodes),
        "allow_user_locked_positions": True,
        "agent_layout_intent": {"status": "planned", "enabled": False},
    }


def _lod_summary(nodes: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "far": sum(1 for node in nodes if node["detail_level"] == "far"),
        "mid": sum(1 for node in nodes if node["detail_level"] == "mid"),
        "near": sum(1 for node in nodes if node["detail_level"] == "near"),
    }


def _resolve_grammar(value: str, base: dict[str, Any]) -> str:
    if value in SPATIAL_GRAMMARS:
        return value
    nodes = [item for item in base.get("nodes", []) if isinstance(item, dict)]
    if str(base.get("level")) == "scene":
        return "stage"
    branch_count = sum(1 for item in nodes if item.get("type") == "branch")
    character_count = sum(1 for item in nodes if item.get("type") == "character")
    question_count = sum(1 for item in nodes if item.get("type") in {"reader-question", "promise"})
    if branch_count >= 3 or character_count >= 5:
        return "braid"
    if question_count >= 4:
        return "constellation"
    return "spine"


def _parent_map(edges: list[dict[str, Any]]) -> dict[str, str]:
    priority = {"sequence": 0, "bridge": 0, "workflow": 1, "branch": 2, "review": 2, "canon": 2, "raises": 3, "promise": 3, "participates": 4}
    selected: dict[str, tuple[int, str]] = {}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not source or not target:
            continue
        weight = priority.get(str(edge.get("type") or ""), 5)
        current = selected.get(target)
        if current is None or (weight, source) < current:
            selected[target] = (weight, source)
    return {target: source for target, (_weight, source) in selected.items()}


def _cluster_id(node: dict[str, Any], grammar: str) -> str:
    node_type = str(node.get("type") or "")
    if node_type in {"chapter", "scene"}:
        return f"narrative:{node.get('order', 0) // 4:03d}"
    if node_type == "character":
        return "characters"
    if node_type in {"branch", "reader-question", "promise"}:
        return "possibilities"
    if node_type in {"review", "canon"}:
        return "evidence"
    if node_type == "task":
        return "work-in-progress"
    return f"{grammar}:{node_type or 'other'}"


def _time_band(node: dict[str, Any], primary_count: int) -> float:
    if node.get("type") not in {"chapter", "scene"}:
        return 0.5
    count = max(primary_count - 1, 1)
    return round(min(1.0, max(0.0, int(node.get("order") or 0) / count)), 4)


def _importance(node: dict[str, Any]) -> float:
    node_type = str(node.get("type") or "")
    status = str(node.get("status") or "")
    base = {
        "scene": 1.0,
        "chapter": 0.96,
        "task": 0.92,
        "branch": 0.76,
        "character": 0.69,
        "canon": 0.66,
        "review": 0.62,
        "promise": 0.58,
        "reader-question": 0.56,
    }.get(node_type, 0.42)
    if status == "blocked":
        base += 0.14
    elif status == "current":
        base += 0.1
    elif status == "formal":
        base += 0.04
    return min(1.0, round(base, 3))


def _detail_level(node: dict[str, Any], primary_count: int) -> str:
    if str(node.get("status")) in {"current", "blocked"} or str(node.get("type")) == "task":
        return "near"
    if primary_count > 80 and str(node.get("type")) in {"chapter", "scene"}:
        return "far"
    return "mid"


def _world_hint(node: dict[str, Any], grammar: str, index: int) -> dict[str, Any]:
    kind = str(node.get("type") or "other")
    surface = {
        "chapter": "spine-segment",
        "scene": "stage-segment",
        "character": "ribbon-anchor",
        "branch": "divergence",
        "canon": "foundation",
        "review": "evidence-surface",
        "promise": "arc",
        "reader-question": "echo",
        "task": "construction-light",
    }.get(kind, "archive-fragment")
    return {
        "surface": surface,
        "grammar": grammar,
        "elevation_band": "foreground" if node.get("status") in {"current", "blocked"} else "midground" if index % 3 else "background",
        "occlusion_priority": _importance(node),
    }


def _edge_strength(edge: dict[str, Any]) -> float:
    return {
        "sequence": 1.0,
        "bridge": 0.96,
        "workflow": 0.92,
        "branch": 0.86,
        "participates": 0.62,
        "canon": 0.7,
        "review": 0.66,
        "promise": 0.68,
        "raises": 0.62,
    }.get(str(edge.get("type") or ""), 0.48)


def _cluster_label(cluster_id: str) -> str:
    labels = {
        "characters": "人物轨迹",
        "possibilities": "可能性与承诺",
        "evidence": "审查与设定证据",
        "work-in-progress": "正在推进",
    }
    if cluster_id.startswith("narrative:"):
        return "叙事段落"
    return labels.get(cluster_id, "作品构件")


def _available_actions(node: dict[str, Any]) -> list[dict[str, str]]:
    actions = [{"id": "focus", "label": "聚焦此节点"}, {"id": "open-detail", "label": "打开节点资料"}]
    if node.get("navigate") == "library":
        actions.append({"id": "open-archive", "label": "查看作品档案"})
    if node.get("status") == "formal":
        actions.append({"id": "open-manuscript", "label": "阅读正式正文"})
    return actions


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
