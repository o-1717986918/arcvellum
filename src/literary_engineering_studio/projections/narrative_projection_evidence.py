"""Evidence and workflow nodes attached to narrative scenes."""

from __future__ import annotations

from typing import Any

from .narrative_projection_models import ProjectionInventory
from .narrative_projection_primitives import digest, edge, fact, friendly_action, node


def append_scene_evidence(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene: dict[str, Any],
    inventory: ProjectionInventory,
    *,
    include_pending: bool,
) -> None:
    scene_id = str(scene.get("id") or "")
    if not scene_id:
        return
    scene_ref = str(scene.get("path") or scene_id)
    _append_branches(nodes, edges, scene_id, scene_ref, inventory.branches, include_pending)
    _append_reviews(nodes, edges, scene_id, scene_ref, inventory.reviews, include_pending)
    _append_canon(nodes, edges, scene_id, inventory.canon_patches)
    _append_reader_contract(nodes, edges, scene, scene_id, scene_ref)


def append_task_projection(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dashboard: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    level: str,
) -> None:
    action = _current_action(dashboard)
    if not action:
        return
    route = str(action.get("route") or "auto")
    target = str(action.get("target") or "")
    task_id = f"task:{route}:{target or digest(action)}"
    nodes.append(node(
        task_id, "task", "下一项创作任务", "queued", "workflow-action", f"{route}:{target}", "overview",
        subtitle=friendly_action(str(action.get("next_action") or "状态机已准备好下一步"))[:90],
    ))
    task_edge = _task_target_edge(task_id, target, scenes, level)
    if task_edge:
        edges.append(task_edge)


def _append_branches(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene_id: str,
    scene_ref: str,
    branches: list[dict[str, Any]],
    include_pending: bool,
) -> None:
    branch = next((item for item in branches if str(item.get("id") or "") == scene_id), None)
    options = _branch_options(branch)
    for option in options:
        _append_branch_option(nodes, edges, scene_id, scene_ref, branch, option)
    if not options and include_pending:
        _append_pending_branch(nodes, edges, scene_id, scene_ref)


def _branch_options(branch: dict[str, Any] | None) -> list[dict[str, Any]]:
    value = branch.get("options") if isinstance(branch, dict) else []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _append_branch_option(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene_id: str,
    scene_ref: str,
    branch: dict[str, Any] | None,
    option: dict[str, Any],
) -> None:
    option_id = str(option.get("id") or digest(option))
    node_id = f"branch:{scene_id}:{option_id}"
    selected = bool(option.get("selected"))
    branch_ref = str(branch.get("path") or scene_ref) if isinstance(branch, dict) else scene_ref
    nodes.append(node(
        node_id, "branch", str(option.get("label") or option_id),
        "formal" if selected else "alternative", "branch", branch_ref, "library",
        subtitle=str(option.get("summary") or "")[:90],
    ))
    edges.append(edge(f"scene:{scene_id}", node_id, "branch", "已选择" if selected else "备选"))


def _append_pending_branch(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene_id: str,
    scene_ref: str,
) -> None:
    node_id = f"branch-pending:{scene_id}"
    nodes.append(node(node_id, "branch", "待推演分支", "blocked", "scene", scene_ref, "overview", subtitle="这一场尚未生成正式分支；完成剧情推演后会在此展开。"))
    edges.append(edge(f"scene:{scene_id}", node_id, "workflow", "等待分支推演"))


def _append_reviews(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene_id: str,
    scene_ref: str,
    reviews: list[dict[str, Any]],
    include_pending: bool,
) -> None:
    related = [item for item in reviews if _review_matches_scene(item, scene_id)]
    for review in related[:2]:
        node_id = f"review:{review.get('id')}"
        status = "formal" if str(review.get("status")) in {"pass", "ready"} else "blocked"
        nodes.append(node(
            node_id, "review", str(review.get("title") or "场景审查"), status,
            "review", str(review.get("path") or review.get("id")), "library",
            subtitle=str(review.get("excerpt") or "")[:90],
        ))
        edges.append(edge(f"scene:{scene_id}", node_id, "review", "审查证据"))
    if include_pending and not related:
        node_id = f"review-pending:{scene_id}"
        nodes.append(node(node_id, "review", "待场景审查", "blocked", "scene", scene_ref, "overview", subtitle="这一场尚未写入候选审查结论；完成 AgentReview 后会在此显示。"))
        edges.append(edge(f"scene:{scene_id}", node_id, "workflow", "等待场景审查"))


def _append_canon(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene_id: str,
    canon_patches: list[dict[str, Any]],
) -> None:
    related = [item for item in canon_patches if scene_id.lower() in _item_reference(item).lower()]
    for patch in related[:3]:
        node_id = f"canon:{patch.get('id')}"
        status = "formal" if str(patch.get("status")) in {"applied", "approved"} else "blocked"
        nodes.append(node(
            node_id, "canon", str(patch.get("title") or "设定变化"), status,
            "canon-patch", str(patch.get("path") or patch.get("id")), "library",
            subtitle=str(patch.get("excerpt") or "")[:90],
        ))
        edges.append(edge(f"scene:{scene_id}", node_id, "canon", "设定写回"))


def _append_reader_contract(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    scene: dict[str, Any],
    scene_id: str,
    scene_ref: str,
) -> None:
    question = fact(scene, "读者问题")
    if question and question != "未填写":
        node_id = f"question:{scene_id}"
        nodes.append(node(node_id, "reader-question", question[:38], "alternative", "scene", scene_ref, "library", subtitle="本场留下的读者问题"))
        edges.append(edge(f"scene:{scene_id}", node_id, "raises", "提出问题"))
    promise = fact(scene, "承诺回报")
    if promise and promise != "未填写":
        node_id = f"promise:{scene_id}"
        nodes.append(node(node_id, "promise", promise[:38], "memory", "scene", scene_ref, "library", subtitle="后续必须兑现、反转或解释"))
        edges.append(edge(f"scene:{scene_id}", node_id, "promise", "建立承诺"))


def _review_matches_scene(review: dict[str, Any], scene_id: str) -> bool:
    reference = _item_reference(review).lower()
    return scene_id.lower() in reference and "agent_completion" not in reference


def _item_reference(item: dict[str, Any]) -> str:
    return str(item.get("path") or item.get("id") or "")


def _current_action(dashboard: dict[str, Any]) -> dict[str, Any] | None:
    actions = dashboard.get("next_actions") if isinstance(dashboard.get("next_actions"), list) else []
    return next((item for item in actions if isinstance(item, dict)), None)


def _task_target_edge(
    task_id: str,
    target: str,
    scenes: list[dict[str, Any]],
    level: str,
) -> dict[str, str] | None:
    scene = next((item for item in scenes if str(item.get("id") or "") == target), None)
    if not scene:
        return None
    if level in {"chapter", "scene"}:
        return edge(task_id, f"scene:{target}", "workflow", "下一步作用于此场景")
    chapter = fact(scene, "章节") or str(scene.get("subtitle") or "")
    return edge(task_id, f"chapter:{chapter}", "workflow", "下一步作用于此章节") if chapter else None


__all__ = ["append_scene_evidence", "append_task_projection"]
