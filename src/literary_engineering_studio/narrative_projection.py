"""Stable, rebuildable graph projection of formal narrative evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .core_read_models import build_dashboard, build_library
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
    sections = library.get("sections") if isinstance(library.get("sections"), dict) else {}
    scenes = [item for item in sections.get("scenes", []) if isinstance(item, dict)]
    characters = [item for item in sections.get("characters", []) if isinstance(item, dict)]
    branches = [item for item in sections.get("branches", []) if isinstance(item, dict)]
    reviews = [item for item in sections.get("reviews", []) if isinstance(item, dict)]
    canon_patches = [item for item in sections.get("canon_patches", []) if isinstance(item, dict)]

    focus_id = _resolve_focus(selected_level, focus, scenes, dashboard)
    if selected_level == "book":
        nodes, edges = _book_graph(scenes, characters, reader, dashboard)
    elif selected_level == "chapter":
        nodes, edges = _chapter_graph(scenes, characters, branches, reader, dashboard, focus_id)
    else:
        nodes, edges = _scene_graph(scenes, characters, branches, reviews, canon_patches, reader, dashboard, focus_id)
    nodes = _dedupe(nodes)
    node_ids = {str(node["node_id"]) for node in nodes}
    edges = [edge for edge in _dedupe_edges(edges) if edge["source"] in node_ids and edge["target"] in node_ids]
    revision_text = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, sort_keys=True)
    projection = {
        "ok": True,
        "schema": PROJECTION_SCHEMA,
        "project_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": hashlib.sha256(revision_text.encode("utf-8")).hexdigest()[:20],
        "sequence": 0,
        "level": selected_level,
        "focus": focus_id,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "scene_count": len(scenes),
            "formal_prose_chars": int(reader.get("total_chinese_content_chars") or 0),
            "aggregated": selected_level == "book" and len(scenes) > 80,
        },
        "nodes": nodes,
        "edges": edges,
        "timeline": _timeline(nodes),
        "delta": projection_delta(None, {"nodes": nodes, "edges": edges}),
        "motion_events": [],
        "legend": [
            {"type": "current", "label": "正在推进", "color": "jade"},
            {"type": "formal", "label": "正式正文与记忆", "color": "brass"},
            {"type": "blocked", "label": "阻塞或待决定", "color": "cinnabar"},
            {"type": "alternative", "label": "备选与不确定", "color": "iris"},
            {"type": "queued", "label": "下一项状态机任务", "color": "moss"},
        ],
        "accessibility_summary": _accessible_summary(selected_level, focus_id, nodes, edges),
    }
    return projection


def projection_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    previous_nodes = {
        str(item.get("node_id")): item
        for item in (previous or {}).get("nodes", [])
        if isinstance(item, dict) and item.get("node_id")
    }
    current_nodes = {
        str(item.get("node_id")): item
        for item in current.get("nodes", [])
        if isinstance(item, dict) and item.get("node_id")
    }
    previous_edges = {
        str(item.get("edge_id")): item
        for item in (previous or {}).get("edges", [])
        if isinstance(item, dict) and item.get("edge_id")
    }
    current_edges = {
        str(item.get("edge_id")): item
        for item in current.get("edges", [])
        if isinstance(item, dict) and item.get("edge_id")
    }
    updated_nodes = sorted(
        node_id for node_id in current_nodes.keys() & previous_nodes.keys() if current_nodes[node_id] != previous_nodes[node_id]
    )
    updated_edges = sorted(
        edge_id for edge_id in current_edges.keys() & previous_edges.keys() if current_edges[edge_id] != previous_edges[edge_id]
    )
    return {
        "initial": previous is None,
        "added_nodes": sorted(current_nodes.keys() - previous_nodes.keys()),
        "removed_nodes": sorted(previous_nodes.keys() - current_nodes.keys()),
        "updated_nodes": updated_nodes,
        "added_edges": sorted(current_edges.keys() - previous_edges.keys()),
        "removed_edges": sorted(previous_edges.keys() - current_edges.keys()),
        "updated_edges": updated_edges,
    }


def projection_motion_events(previous: dict[str, Any] | None, current: dict[str, Any], delta: dict[str, Any]) -> list[dict[str, str]]:
    current_nodes = {str(item.get("node_id")): item for item in current.get("nodes", []) if isinstance(item, dict)}
    previous_nodes = {str(item.get("node_id")): item for item in (previous or {}).get("nodes", []) if isinstance(item, dict)}
    events: list[dict[str, str]] = []
    for node_id in delta.get("added_nodes", []):
        node = current_nodes.get(str(node_id), {})
        kind = "branch-grown" if node.get("type") == "branch" else "node-grown"
        events.append({"type": kind, "node_id": str(node_id), "label": str(node.get("label") or "新叙事节点")})
    for node_id in delta.get("updated_nodes", []):
        before = previous_nodes.get(str(node_id), {})
        after = current_nodes.get(str(node_id), {})
        if after.get("status") == "formal" and before.get("status") != "formal":
            events.append({"type": "joined-canon", "node_id": str(node_id), "label": str(after.get("label") or "并入正式长卷")})
        before_chars = int((before.get("metrics") or {}).get("formal_chars") or 0)
        after_chars = int((after.get("metrics") or {}).get("formal_chars") or 0)
        if after_chars > before_chars:
            events.append({"type": "manuscript-grown", "node_id": str(node_id), "label": f"正文增加 {after_chars - before_chars:,} 字"})
        if after.get("type") == "canon" and after.get("status") == "formal":
            events.append({"type": "canon-anchored", "node_id": str(node_id), "label": str(after.get("label") or "设定已写回")})
    for node in current.get("nodes", []):
        if isinstance(node, dict) and node.get("type") == "task" and node.get("status") == "queued":
            events.append({"type": "task-pulse", "node_id": str(node.get("node_id") or ""), "label": str(node.get("subtitle") or "当前任务")})
            break
    return events[:12]


def _timeline(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": str(node.get("node_id") or ""),
            "label": str(node.get("label") or ""),
            "status": str(node.get("status") or "planned"),
            "order": int(node.get("order") or 0),
            "formal_chars": int((node.get("metrics") or {}).get("formal_chars") or 0),
            "word_target": int((node.get("metrics") or {}).get("word_target") or 0),
        }
        for node in sorted(nodes, key=lambda item: (int(item.get("order") or 0), str(item.get("node_id") or "")))
        if node.get("type") in {"chapter", "scene"}
    ]


def _book_graph(
    scenes: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    reader: dict[str, Any],
    dashboard: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chapters: dict[str, list[dict[str, Any]]] = {}
    for scene in scenes:
        chapter = _fact(scene, "章节") or str(scene.get("subtitle") or "未分章")
        chapters.setdefault(chapter, []).append(scene)
    formal_coverage = {
        scene_id
        for unit in reader.get("units", [])
        if isinstance(unit, dict)
        for scene_id in unit.get("coverage", [])
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    ordered = sorted(chapters, key=_order)
    formal_chars = _formal_chars_by_chapter(reader)
    for index, chapter in enumerate(ordered):
        chapter_scenes = chapters[chapter]
        promoted = sum(1 for scene in chapter_scenes if str(scene.get("id")) in formal_coverage)
        target = sum(_integer(_fact(scene, "目标字数")) for scene in chapter_scenes)
        actual = formal_chars.get(chapter, 0)
        nodes.append(
            _node(
                f"chapter:{chapter}",
                "chapter",
                _chapter_label(chapter),
                "formal" if promoted == len(chapter_scenes) and promoted else "current" if promoted else "planned",
                "scene-catalog",
                chapter,
                "overview",
                subtitle=f"{len(chapter_scenes)} 场 · 正文 {actual:,} 字",
                metrics={"scene_count": len(chapter_scenes), "promoted_count": promoted, "word_target": target, "formal_chars": actual},
                order=index,
            )
        )
        if index:
            edges.append(_edge(f"chapter:{ordered[index - 1]}", f"chapter:{chapter}", "sequence", "章节推进"))
    for character in [item for item in characters if str(item.get("status")) == "major"][:12]:
        character_id = str(character.get("id") or "")
        nodes.append(_node(f"character:{character_id}", "character", str(character.get("title") or character_id), "memory", "character", str(character.get("path") or character_id), "library", subtitle=str(character.get("subtitle") or "主要人物")))
        for chapter, chapter_scenes in chapters.items():
            if any(str(character.get("title") or "") in _fact(scene, "参与者") for scene in chapter_scenes):
                edges.append(_edge(f"character:{character_id}", f"chapter:{chapter}", "participates", "人物弧进入章节"))
    _append_task_projection(nodes, edges, dashboard, scenes, level="book")
    return nodes, edges


def _chapter_graph(
    scenes: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    branches: list[dict[str, Any]],
    reader: dict[str, Any],
    dashboard: dict[str, Any],
    chapter_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = [scene for scene in scenes if (_fact(scene, "章节") or str(scene.get("subtitle") or "")) == chapter_id]
    selected.sort(key=lambda item: _order(str(item.get("id") or "")))
    formal = {scene_id for unit in reader.get("units", []) if isinstance(unit, dict) for scene_id in unit.get("coverage", [])}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    participant_names: set[str] = set()
    for index, scene in enumerate(selected[:80]):
        scene_id = str(scene.get("id") or "")
        status = "formal" if scene_id in formal else "blocked" if str(scene.get("status")) == "blocked" else "current" if index == 0 else "planned"
        nodes.append(_node(f"scene:{scene_id}", "scene", str(scene.get("title") or scene_id), status, "scene", str(scene.get("path") or scene_id), "library", subtitle=str(scene.get("excerpt") or "")[:90], metrics={"word_target": _integer(_fact(scene, "目标字数"))}, order=index))
        participant_names.update(part.strip() for part in re.split(r"[、,，]", _fact(scene, "参与者")) if part.strip())
        if index:
            edges.append(_edge(f"scene:{selected[index - 1].get('id')}", f"scene:{scene_id}", "bridge", "场景承接"))
        question = _fact(scene, "读者问题")
        if question and question != "未填写":
            promise_id = f"question:{scene_id}"
            nodes.append(_node(promise_id, "reader-question", question[:38], "alternative", "scene", str(scene.get("path") or scene_id), "library", subtitle="读者带入下一场的问题"))
            edges.append(_edge(f"scene:{scene_id}", promise_id, "raises", "提出问题"))
        promised_reward = _fact(scene, "承诺回报")
        if promised_reward and promised_reward != "未填写":
            promise_id = f"promise:{scene_id}"
            nodes.append(_node(promise_id, "promise", promised_reward[:38], "memory", "scene", str(scene.get("path") or scene_id), "library", subtitle="作品向读者作出的后续承诺"))
            edges.append(_edge(f"scene:{scene_id}", promise_id, "promise", "建立承诺"))
    for character in characters:
        if str(character.get("title") or "") not in participant_names:
            continue
        character_id = str(character.get("id") or "")
        nodes.append(_node(f"character:{character_id}", "character", str(character.get("title") or character_id), "memory", "character", str(character.get("path") or character_id), "library", subtitle=str(character.get("subtitle") or "")))
        for scene in selected:
            if str(character.get("title") or "") in _fact(scene, "参与者"):
                edges.append(_edge(f"character:{character_id}", f"scene:{scene.get('id')}", "participates", "参与"))
    for branch in branches:
        scene_id = str(branch.get("id") or "")
        if not any(str(scene.get("id")) == scene_id for scene in selected):
            continue
        for option in branch.get("options", []) if isinstance(branch.get("options"), list) else []:
            if not isinstance(option, dict):
                continue
            option_id = str(option.get("id") or _digest(option))
            nodes.append(_node(f"branch:{scene_id}:{option_id}", "branch", str(option.get("label") or option_id), "formal" if option.get("selected") else "alternative", "branch", str(branch.get("path") or scene_id), "library", subtitle=str(option.get("summary") or "")[:90]))
            edges.append(_edge(f"scene:{scene_id}", f"branch:{scene_id}:{option_id}", "branch", "已选择" if option.get("selected") else "备选"))
    _append_task_projection(nodes, edges, dashboard, selected, level="chapter")
    return nodes, edges


def _scene_graph(
    scenes: list[dict[str, Any]],
    characters: list[dict[str, Any]],
    branches: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    canon_patches: list[dict[str, Any]],
    reader: dict[str, Any],
    dashboard: dict[str, Any],
    scene_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scene = next((item for item in scenes if str(item.get("id")) == scene_id), None)
    if scene is None:
        return [], []
    formal = any(scene_id in unit.get("coverage", []) for unit in reader.get("units", []) if isinstance(unit, dict))
    nodes = [_node(f"scene:{scene_id}", "scene", str(scene.get("title") or scene_id), "formal" if formal else "current", "scene", str(scene.get("path") or scene_id), "library", subtitle=str(scene.get("excerpt") or ""), metrics={"word_target": _integer(_fact(scene, "目标字数"))}, order=0)]
    edges: list[dict[str, Any]] = []
    participants = {part.strip() for part in re.split(r"[、,，]", _fact(scene, "参与者")) if part.strip()}
    for character in characters:
        if str(character.get("title") or "") not in participants:
            continue
        item_id = str(character.get("id") or "")
        nodes.append(_node(f"character:{item_id}", "character", str(character.get("title") or item_id), "memory", "character", str(character.get("path") or item_id), "library", subtitle=str(character.get("excerpt") or "")[:90]))
        edges.append(_edge(f"character:{item_id}", f"scene:{scene_id}", "participates", "参与本场"))
    branch = next((item for item in branches if str(item.get("id")) == scene_id), None)
    if branch:
        for option in branch.get("options", []) if isinstance(branch.get("options"), list) else []:
            if not isinstance(option, dict):
                continue
            option_id = str(option.get("id") or _digest(option))
            node_id = f"branch:{scene_id}:{option_id}"
            nodes.append(_node(node_id, "branch", str(option.get("label") or option_id), "formal" if option.get("selected") else "alternative", "branch", str(branch.get("path") or scene_id), "library", subtitle=str(option.get("summary") or "")[:90]))
            edges.append(_edge(f"scene:{scene_id}", node_id, "branch", "采用" if option.get("selected") else "舍弃/保留"))
    related_reviews = [item for item in reviews if scene_id.lower() in str(item.get("path") or item.get("id") or "").lower()]
    for review in related_reviews[:2]:
        node_id = f"review:{review.get('id')}"
        status = "formal" if str(review.get("status")) in {"pass", "ready"} else "blocked"
        nodes.append(_node(node_id, "review", str(review.get("title") or "场景审查"), status, "review", str(review.get("path") or review.get("id")), "library", subtitle=str(review.get("excerpt") or "")[:90]))
        edges.append(_edge(f"scene:{scene_id}", node_id, "review", "审查证据"))
    for patch in [item for item in canon_patches if scene_id.lower() in str(item.get("path") or item.get("id") or "").lower()][:3]:
        node_id = f"canon:{patch.get('id')}"
        nodes.append(_node(node_id, "canon", str(patch.get("title") or "设定变化"), "formal" if str(patch.get("status")) in {"applied", "approved"} else "blocked", "canon-patch", str(patch.get("path") or patch.get("id")), "library", subtitle=str(patch.get("excerpt") or "")[:90]))
        edges.append(_edge(f"scene:{scene_id}", node_id, "canon", "设定写回"))
    question = _fact(scene, "读者问题")
    if question and question != "未填写":
        node_id = f"question:{scene_id}"
        nodes.append(_node(node_id, "reader-question", question[:38], "alternative", "scene", str(scene.get("path") or scene_id), "library", subtitle="本场留下的读者问题"))
        edges.append(_edge(f"scene:{scene_id}", node_id, "raises", "提出问题"))
    promised_reward = _fact(scene, "承诺回报")
    if promised_reward and promised_reward != "未填写":
        node_id = f"promise:{scene_id}"
        nodes.append(_node(node_id, "promise", promised_reward[:38], "memory", "scene", str(scene.get("path") or scene_id), "library", subtitle="后续必须兑现、反转或解释"))
        edges.append(_edge(f"scene:{scene_id}", node_id, "promise", "建立承诺"))
    _append_task_projection(nodes, edges, dashboard, [scene], level="scene")
    return nodes, edges


def _formal_chars_by_chapter(reader: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for unit in reader.get("units", []) if isinstance(reader.get("units"), list) else []:
        if not isinstance(unit, dict):
            continue
        chapter_id = str(unit.get("chapter_id") or "")
        if chapter_id:
            result[chapter_id] = result.get(chapter_id, 0) + int(unit.get("chinese_content_chars") or 0)
    return result


def _append_task_projection(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dashboard: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    level: str,
) -> None:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    action = next((item for item in actions if isinstance(item, dict)), None)
    if not action:
        return
    route = str(action.get("route") or "auto")
    target = str(action.get("target") or "")
    task_id = f"task:{route}:{target or _digest(action)}"
    nodes.append(
        _node(
            task_id,
            "task",
            "下一项创作任务",
            "queued",
            "workflow-action",
            f"{route}:{target}",
            "overview",
            subtitle=_friendly_action(str(action.get("next_action") or "状态机已准备好下一步"))[:90],
        )
    )
    scene = next((item for item in scenes if str(item.get("id") or "") == target), None)
    if scene and level in {"chapter", "scene"}:
        edges.append(_edge(task_id, f"scene:{target}", "workflow", "下一步作用于此场景"))
    elif scene and level == "book":
        chapter = _fact(scene, "章节") or str(scene.get("subtitle") or "")
        if chapter:
            edges.append(_edge(task_id, f"chapter:{chapter}", "workflow", "下一步作用于此章节"))


def _node(node_id: str, node_type: str, label: str, status: str, source_type: str, source_id: str, navigate: str, *, subtitle: str = "", metrics: dict[str, Any] | None = None, order: int = 0) -> dict[str, Any]:
    return {"node_id": node_id, "type": node_type, "label": label, "subtitle": subtitle, "status": status, "source_type": source_type, "source_id": source_id, "navigate": navigate, "metrics": metrics or {}, "order": order}


def _edge(source: str, target: str, edge_type: str, label: str) -> dict[str, str]:
    return {"edge_id": f"{edge_type}:{source}>{target}", "source": source, "target": target, "type": edge_type, "label": label}


def _resolve_focus(level: str, focus: str, scenes: list[dict[str, Any]], dashboard: dict[str, Any]) -> str:
    if focus:
        return focus
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    target = next((str(item.get("target")) for item in actions if isinstance(item, dict) and str(item.get("target", "")).startswith("scene")), "")
    if level == "scene":
        return target or (str(scenes[0].get("id")) if scenes else "")
    if level == "chapter":
        scene = next((item for item in scenes if str(item.get("id")) == target), scenes[0] if scenes else {})
        return _fact(scene, "章节") or str(scene.get("subtitle") or "")
    return "book"


def _fact(item: dict[str, Any], label: str) -> str:
    for fact in item.get("facts", []) if isinstance(item.get("facts"), list) else []:
        if isinstance(fact, dict) and str(fact.get("label")) == label:
            return str(fact.get("value") or "")
    return ""


def _dedupe(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        result.setdefault(str(node["node_id"]), node)
    return list(result.values())


def _dedupe_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for edge in edges:
        result.setdefault(edge["edge_id"], edge)
    return list(result.values())


def _order(value: str) -> tuple[int, str]:
    values = re.findall(r"\d+", value or "")
    return (int(values[-1]) if values else 10**9, value)


def _integer(value: str) -> int:
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else 0


def _chapter_label(chapter_id: str) -> str:
    number = _order(chapter_id)[0]
    return f"第 {number} 章" if number < 10**9 else chapter_id


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _friendly_action(value: str) -> str:
    lowered = value.lower()
    labels = (
        ("context", "整理这一场所需的人物、设定和前情"),
        ("simulate-scene", "推演角色在当前处境中的选择"),
        ("branch-simulate", "比较可行的剧情分支"),
        ("compose-scene", "形成这一场的写作方案"),
        ("generate-scene", "创作这一场的正文"),
        ("agent-review-scene", "审读并核验这一场正文"),
        ("promote", "确认正文进入正式长卷"),
        ("state-evolve", "更新人物状态与剧情后果"),
    )
    for token, label in labels:
        if token in lowered:
            return label
    if "--" in value or lowered.startswith("lew ") or lowered.startswith("run "):
        return "状态机已准备好下一项创作工作"
    return value


def _accessible_summary(level: str, focus: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    blocked = sum(1 for node in nodes if node.get("status") == "blocked")
    formal = sum(1 for node in nodes if node.get("status") == "formal")
    level_label = {"book": "全书", "chapter": "章节", "scene": "当前场景"}.get(level, "叙事")
    return f"{level_label}视图，共 {len(nodes)} 个节点、{len(edges)} 条关系；{formal} 个正式节点，{blocked} 个阻塞或待决定节点。"
