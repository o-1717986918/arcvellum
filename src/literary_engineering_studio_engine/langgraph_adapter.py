"""LangGraph adapter for the file-backed literary workflow runner."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from .workflow_runner import run_workflow


class LiteraryWorkflowState(TypedDict, total=False):
    project_root: str
    scene: str
    chapter_id: str
    target_length: int
    include_blocked: bool
    overwrite_draft: bool
    generate_candidate: bool
    promote_candidate: bool
    agent_review: bool
    provider: str
    thread_id: str
    status: str
    scene_loop_run_id: str
    scene_loop_state: str
    chapter_publish_run_id: str
    chapter_publish_state: str
    workflow_log: str


STATUS_PRIORITY = {
    "completed": 0,
    "completed_with_skips": 1,
    "blocked": 2,
    "failed": 3,
}


def is_langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def build_literary_graph():
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("LangGraph adapter requires optional dependency: langgraph") from exc

    graph = StateGraph(LiteraryWorkflowState)
    graph.add_node("scene_loop", _scene_loop_node)
    graph.add_node("chapter_publish", _chapter_publish_node)
    graph.add_edge(START, "scene_loop")
    graph.add_edge("scene_loop", "chapter_publish")
    graph.add_edge("chapter_publish", END)
    return graph.compile()


def run_literary_graph(
    project_root: Path,
    scene: Path = Path("scenes/scene_0001.yaml"),
    chapter_id: str = "chapter_0001",
    target_length: int = 100000,
    include_blocked: bool = False,
    overwrite_draft: bool = False,
    generate_candidate: bool = False,
    promote_candidate: bool = False,
    agent_review: bool = False,
    provider: str = "auto",
    thread_id: str = "",
) -> LiteraryWorkflowState:
    graph = build_literary_graph()
    resolved_thread_id = thread_id or f"lew-{uuid4().hex[:12]}"
    state: LiteraryWorkflowState = {
        "project_root": str(project_root),
        "scene": str(scene),
        "chapter_id": chapter_id,
        "target_length": target_length,
        "include_blocked": include_blocked,
        "overwrite_draft": overwrite_draft,
        "generate_candidate": generate_candidate,
        "promote_candidate": promote_candidate,
        "agent_review": agent_review,
        "provider": provider,
        "thread_id": resolved_thread_id,
        "status": "running",
    }
    return graph.invoke(state, config={"configurable": {"thread_id": resolved_thread_id}})


def _scene_loop_node(state: LiteraryWorkflowState) -> LiteraryWorkflowState:
    root = Path(state["project_root"])
    result = run_workflow(
        root,
        mode="scene-loop",
        scene=Path(state.get("scene") or "scenes/scene_0001.yaml"),
        chapter_id=state.get("chapter_id") or "chapter_0001",
        target_length=int(state.get("target_length") or 100000),
        include_blocked=bool(state.get("include_blocked", False)),
        overwrite_draft=bool(state.get("overwrite_draft", False)),
        generate_candidate=bool(state.get("generate_candidate", False)),
        promote_candidate=bool(state.get("promote_candidate", False)),
        agent_review=bool(state.get("agent_review", False)),
        provider=state.get("provider") or "auto",
    )
    return {
        **state,
        "status": _combine_status(state.get("status", "completed"), result.status),
        "scene_loop_run_id": result.run_id,
        "scene_loop_state": str(result.state_path),
        "workflow_log": str(result.log_path),
    }


def _chapter_publish_node(state: LiteraryWorkflowState) -> LiteraryWorkflowState:
    root = Path(state["project_root"])
    result = run_workflow(
        root,
        mode="chapter-publish",
        scene=Path(state.get("scene") or "scenes/scene_0001.yaml"),
        chapter_id=state.get("chapter_id") or "chapter_0001",
        target_length=int(state.get("target_length") or 100000),
        include_blocked=bool(state.get("include_blocked", False)),
        overwrite_draft=False,
        generate_candidate=False,
        promote_candidate=False,
        agent_review=bool(state.get("agent_review", False)),
        provider=state.get("provider") or "auto",
    )
    return {
        **state,
        "status": _combine_status(state.get("status", "completed"), result.status),
        "chapter_publish_run_id": result.run_id,
        "chapter_publish_state": str(result.state_path),
        "workflow_log": str(result.log_path),
    }


def _combine_status(previous: str, current: str) -> str:
    previous_priority = STATUS_PRIORITY.get(previous, 0)
    current_priority = STATUS_PRIORITY.get(current, 0)
    return previous if previous_priority >= current_priority else current
