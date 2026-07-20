"""Dependency-free workflow runner for future agent orchestration adapters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from .agent_tasks import agent_task_completion_status, default_agent_tasks_path
from .branch_lab import build_branch_simulation
from .candidate_promotion import promote_scene_candidate
from .character_state_evolver import build_character_state_patch
from .chapter_pipeline import build_chapter_workspace
from .context_packet import build_context_packet
from .export_package import build_export_package
from .flow_gates import FlowGateError, branch_selection_status
from .longform_audit import build_longform_audit
from .memory_index import build_memory_index
from .platform_agent_tasks import (
    write_platform_asset_creation_task,
    write_platform_asset_review_task,
    write_platform_canon_review_task,
    write_platform_committee_task,
    write_platform_scene_generation_task,
    write_platform_scene_review_task,
)
from .prompt_pack import build_scene_prompt_pack, write_prompt_manifest
from .review_ci import review_scene_draft
from .roleplay_lab import build_roleplay_simulation
from .scene_composer import build_scene_composition
from .scene_draft import build_scene_draft


WORKFLOW_MODES = {"scene-loop", "chapter-publish", "full-cycle", "project-seeding", "character-lab", "worldbuilding-lab", "outline-lab"}


@dataclass
class WorkflowEvent:
    node_id: str
    status: str
    started_at: str
    ended_at: str
    artifacts: dict[str, str] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class WorkflowRunResult:
    project_root: Path
    run_id: str
    status: str
    state_path: Path
    log_path: Path
    node_count: int
    blocked: bool
    resumed_from: str = ""


@dataclass
class WorkflowState:
    schema: str
    run_id: str
    mode: str
    project_root: str
    scene: str
    chapter_id: str
    status: str
    started_at: str
    ended_at: str
    human_approval_required: bool
    events: list[WorkflowEvent]
    resumed_from: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def run_workflow(
    project_root: Path,
    mode: str = "full-cycle",
    scene: Path | None = None,
    chapter_id: str = "chapter_0001",
    target_length: int = 100000,
    include_blocked: bool = False,
    overwrite_draft: bool = False,
    generate_candidate: bool = False,
    promote_candidate: bool = False,
    agent_review: bool = False,
    agent_tasks: bool = False,
    provider: str = "auto",
    output_dir: Path | None = None,
    run_id: str | None = None,
    resumed_from: str = "",
    overwrite_run: bool = False,
    brief: str = "",
) -> WorkflowRunResult:
    if mode not in WORKFLOW_MODES:
        raise ValueError(f"unknown workflow mode: {mode}. valid: {', '.join(sorted(WORKFLOW_MODES))}")

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = _resolve_scene(root, scene) if mode in {"scene-loop", "chapter-publish", "full-cycle"} else None
    run_id = _validate_run_id(run_id) if run_id else _run_id()
    resumed_from = _validate_run_id(resumed_from) if resumed_from else ""
    if resumed_from:
        _require_existing_run(root, resumed_from)
    run_dir = _resolve_output_dir(root, output_dir, run_id)
    if (run_dir / "workflow_state.json").exists() and not overwrite_run:
        raise FileExistsError(f"workflow run already exists: {run_id}. pass overwrite_run=True to replace it")
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now()
    state = WorkflowState(
        schema="literary-engineering-workbench/workflow-run/v0.1",
        run_id=run_id,
        mode=mode,
        project_root=str(root),
        scene=_rel_str(scene_path, root) if scene_path else "",
        chapter_id=chapter_id,
        status="running",
        started_at=started_at,
        ended_at="",
        human_approval_required=False,
        resumed_from=resumed_from,
        events=[],
    )

    try:
        if mode in {"project-seeding", "character-lab", "worldbuilding-lab", "outline-lab"}:
            _run_asset_workflow(root, mode, state, provider, brief)
        if mode in {"scene-loop", "full-cycle"}:
            _run_scene_loop(root, scene_path, state, overwrite_draft, generate_candidate, promote_candidate, agent_review, agent_tasks, provider)
        if mode in {"chapter-publish", "full-cycle"}:
            _run_chapter_publish(root, chapter_id, target_length, include_blocked, agent_review, provider, state)
    except FlowGateError as exc:
        state.status = "blocked"
        state.human_approval_required = True
        state.warnings.append(f"workflow blocked: {exc}")
        state.events.append(
            WorkflowEvent(
                node_id="workflow_gate",
                status="blocked",
                started_at=_now(),
                ended_at=_now(),
                message=str(exc),
            )
        )
    except Exception as exc:
        state.status = "failed"
        state.warnings.append(f"workflow failed: {exc}")
        state.events.append(
            WorkflowEvent(
                node_id="workflow_error",
                status="failed",
                started_at=_now(),
                ended_at=_now(),
                message=str(exc),
            )
        )
    finally:
        if state.status == "running":
            state.status = _final_status(state)
        state.ended_at = _now()
        state_path = run_dir / "workflow_state.json"
        log_path = run_dir / "workflow_log.md"
        state_path.write_text(_state_json(state), encoding="utf-8")
        log_path.write_text(_render_log(state), encoding="utf-8")
        _append_run_index(root, state, state_path, log_path)

    blocked = state.status in {"blocked", "failed"}
    return WorkflowRunResult(
        project_root=root,
        run_id=run_id,
        status=state.status,
        state_path=state_path,
        log_path=log_path,
        node_count=len(state.events),
        blocked=blocked,
        resumed_from=resumed_from,
    )


def load_workflow_state(project_root: Path, run_id: str) -> dict[str, object]:
    root = project_root.resolve()
    safe_run_id = _validate_run_id(run_id)
    state_path = root / "workflow" / "runs" / safe_run_id / "workflow_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"workflow run not found: {safe_run_id}")
    return json.loads(state_path.read_text(encoding="utf-8"))


def _run_scene_loop(
    root: Path,
    scene_path: Path,
    state: WorkflowState,
    overwrite_draft: bool,
    generate_candidate: bool,
    promote_candidate: bool,
    agent_review: bool,
    agent_tasks: bool,
    provider: str,
) -> None:
    if scene_path is None:
        raise FileNotFoundError("scene is required for scene-loop")
    scene_id = scene_path.stem
    draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"

    def node(node_id: str, func):
        _run_node(state, node_id, func)

    node("retrieve_memory", lambda: _artifact("index", build_memory_index(root).index_path, root))
    node(
        "build_context_packet",
        lambda: _context_artifact(root, scene_path),
    )
    node(
        "character_simulation",
        lambda: _simulation_artifact(root, scene_path, agent_tasks),
    )
    if agent_tasks and _block_on_pending_agent_task(state, root, "character_simulation_handoff", "simulation_agent_tasks"):
        return
    node(
        "branch_simulation",
        lambda: _branch_artifact(root, scene_path, agent_tasks),
    )
    if state.events[-1].status != "completed":
        return
    if agent_tasks and _block_on_pending_agent_task(state, root, "branch_simulation_handoff", "branch_agent_tasks"):
        return
    branch_selection = state.artifacts.get("branch_selection", "")
    selection_path = root / branch_selection if branch_selection else root / "branches" / scene_id / "branch_selection.md"
    selection_status = branch_selection_status(selection_path)
    composition_ready = False
    if selection_status["status"] == "selected":
        node(
            "scene_composition",
            lambda: _composition_artifact(root, scene_path, agent_tasks),
        )
        composition_ready = state.events[-1].status == "completed" and bool(state.artifacts.get("scene_composition"))
        if agent_tasks and _block_on_pending_agent_task(state, root, "scene_composition_handoff", "scene_composition_agent_tasks"):
            return
    else:
        artifacts = {"branch_selection": branch_selection} if branch_selection else {}
        message = (
            "formal branch selection pending; fill branch_selection.md with decision: selected and selected_branch "
            "before scene_composition or generate_candidate"
        )
        if generate_candidate:
            _block_node(state, "scene_composition", artifacts, message)
        else:
            _skip_node(state, "scene_composition", artifacts, message)
            state.human_approval_required = True
    if generate_candidate:
        if not composition_ready:
            _block_node(
                state,
                "generate_candidate",
                {"branch_selection": branch_selection} if branch_selection else {},
                "scene composition is missing or not formally selected; generation task blocked",
            )
        else:
            node(
                "generate_candidate",
                lambda: _generation_artifact(root, scene_path, provider, agent_tasks),
            )
            if agent_tasks and _block_on_pending_agent_task(state, root, "candidate_generation_handoff", "candidate_task"):
                return
    if promote_candidate:
        promotion_candidate = state.artifacts.get("candidate", "") or state.artifacts.get("expected_candidate", "")
        if promotion_candidate and not _artifact_exists(root, promotion_candidate):
            _skip_node(
                state,
                "promote_candidate",
                {"expected_candidate": promotion_candidate},
                "platform-agent candidate not written yet; promotion deferred",
            )
            state.human_approval_required = True
        else:
            node(
                "promote_candidate",
                lambda: _promotion_artifact(root, scene_path, promotion_candidate, overwrite_draft),
            )

    if draft_path.exists() and not overwrite_draft:
        _skip_node(
            state,
            "draft_workspace",
            {"draft": _rel_str(draft_path, root)},
            "existing draft preserved; pass --overwrite-draft to regenerate",
        )
    else:
        node("draft_workspace", lambda: _draft_artifact(root, scene_path))

    if draft_path.exists():
        node("review_ci", lambda: _review_artifact(root, draft_path))
        if agent_review:
            node("agent_scene_review", lambda: _agent_scene_review_artifact(root, scene_path, draft_path, provider))
            node("agent_committee", lambda: _agent_committee_artifact(root, scene_id, draft_path, provider))
            state.human_approval_required = True
            state.warnings.append("platform agent review tasks were written; complete their JSON reports before chapter readiness.")
        node("state_evolution_patch", lambda: _state_patch_artifact(root, scene_path, draft_path, agent_tasks))
        if agent_tasks:
            _block_on_pending_agent_task(state, root, "state_evolution_handoff", "state_patch_agent_tasks")
    else:
        _skip_node(state, "review_ci", {}, "draft missing; review skipped")
        _skip_node(state, "state_evolution_patch", {}, "draft missing; state evolution skipped")
        state.human_approval_required = True


def _run_chapter_publish(
    root: Path,
    chapter_id: str,
    target_length: int,
    include_blocked: bool,
    agent_review: bool,
    provider: str,
    state: WorkflowState,
) -> None:
    _run_node(
        state,
        "chapter_workspace",
        lambda: _chapter_artifact(root, chapter_id, agent_review),
    )
    _run_node(
        state,
        "longform_audit",
        lambda: _longform_artifact(root, target_length),
    )
    if agent_review:
        _run_node(
            state,
            "agent_canon_review",
            lambda: _agent_canon_review_artifact(root, provider),
        )
        state.human_approval_required = True
        state.warnings.append("platform agent canon review task was written; complete it before publication.")
    _run_node(
        state,
        "export_package",
        lambda: _export_artifact(root, chapter_id, include_blocked),
    )


def _run_asset_workflow(root: Path, mode: str, state: WorkflowState, provider: str, brief_override: str = "") -> None:
    brief = brief_override.strip() or _project_brief(root)
    plan = {
        "project-seeding": ["world", "character", "outline"],
        "character-lab": ["character", "background-story", "relationship"],
        "worldbuilding-lab": ["world", "location", "organization"],
        "outline-lab": ["outline", "chapter-plan", "scene-list"],
    }[mode]
    for asset_type in plan:
        key = asset_type.replace("-", "_")
        _run_node(
            state,
            f"agent_create_{asset_type.replace('-', '_')}",
            lambda asset_type=asset_type: _asset_candidate_artifact(root, asset_type, provider, brief),
        )
        latest = state.artifacts.get(f"{key}_candidate_expected", "")
        if latest:
            _run_node(
                state,
                f"review_{asset_type.replace('-', '_')}_candidate",
                lambda latest=latest: _asset_review_artifact(root, latest, provider),
            )
    state.human_approval_required = True
    state.warnings.append("asset workflow wrote platform-agent creation/review tasks only; platform agent must fill candidates before promotion.")


def _run_node(state: WorkflowState, node_id: str, func) -> None:
    started = _now()
    try:
        artifacts, message = func()
        status = "completed"
    except FlowGateError as exc:
        artifacts = {}
        message = str(exc)
        status = "blocked"
        state.human_approval_required = True
    except Exception as exc:
        artifacts = {}
        message = str(exc)
        status = "failed"
        state.human_approval_required = True
    ended = _now()
    state.events.append(WorkflowEvent(node_id=node_id, status=status, started_at=started, ended_at=ended, artifacts=artifacts, message=message))
    state.artifacts.update(artifacts)


def _skip_node(state: WorkflowState, node_id: str, artifacts: dict[str, str], message: str) -> None:
    now = _now()
    state.events.append(WorkflowEvent(node_id=node_id, status="skipped", started_at=now, ended_at=now, artifacts=artifacts, message=message))
    state.artifacts.update(artifacts)


def _block_node(state: WorkflowState, node_id: str, artifacts: dict[str, str], message: str) -> None:
    now = _now()
    state.human_approval_required = True
    state.events.append(WorkflowEvent(node_id=node_id, status="blocked", started_at=now, ended_at=now, artifacts=artifacts, message=message))
    state.artifacts.update(artifacts)


def _block_on_pending_agent_task(state: WorkflowState, root: Path, node_id: str, artifact_key: str) -> bool:
    rel_task = state.artifacts.get(artifact_key, "")
    if not rel_task:
        return False
    task_path = root / rel_task
    status = agent_task_completion_status(task_path, root=root)
    if status.get("complete"):
        return False
    artifacts = {artifact_key: rel_task}
    completion_marker = str(status.get("completion_marker") or "")
    if completion_marker:
        artifacts[f"{artifact_key}_completion_marker"] = completion_marker
    _block_node(
        state,
        node_id,
        artifacts,
        f"platform-agent task pending: {status.get('message') or status.get('status')}. Complete {rel_task} before the next formal step.",
    )
    return True


def _artifact(key: str, path: Path, root: Path) -> tuple[dict[str, str], str]:
    return {key: _rel_str(path, root)}, "ok"


def _context_artifact(root: Path, scene_path: Path) -> tuple[dict[str, str], str]:
    result = build_context_packet(root, scene=scene_path, rebuild_index=True)
    artifacts = {"context_packet": _rel_str(result.output_path, root)}
    if result.trace_path:
        artifacts["context_trace"] = _rel_str(result.trace_path, root)
    return artifacts, f"retrievals={result.retrieval_count}"


def _simulation_artifact(root: Path, scene_path: Path, agent_tasks: bool) -> tuple[dict[str, str], str]:
    scene_id = scene_path.stem
    existing = root / "branches" / scene_id / "roleplay_simulation.md"
    if existing.exists():
        text = existing.read_text(encoding="utf-8", errors="ignore")
        if "读取回执" in text and "[AGENT_TASK:" not in text:
            artifacts = {"simulation": _rel_str(existing, root)}
            task_path = default_agent_tasks_path(existing)
            if agent_tasks and task_path.exists():
                artifacts["simulation_agent_tasks"] = _rel_str(task_path, root)
            return artifacts, "existing platform-agent roleplay receipt preserved"
    result = build_roleplay_simulation(root, scene=scene_path, rebuild_context=False, agent_mode=agent_tasks)
    artifacts = {"simulation": _rel_str(result.output_path, root)}
    if result.agent_tasks_path:
        artifacts["simulation_agent_tasks"] = _rel_str(result.agent_tasks_path, root)
    return artifacts, f"characters={result.character_count}"


def _branch_artifact(root: Path, scene_path: Path, agent_tasks: bool) -> tuple[dict[str, str], str]:
    result = build_branch_simulation(root, scene=scene_path, rebuild_context=False, agent_tasks=agent_tasks)
    artifacts = {
        "branch_simulation": _rel_str(result.output_path, root),
        "branch_manifest": _rel_str(result.manifest_path, root),
        "branch_selection": _rel_str(result.selection_path, root),
    }
    if result.agent_tasks_path:
        artifacts["branch_agent_tasks"] = _rel_str(result.agent_tasks_path, root)
    return artifacts, f"branches={result.branch_count}; recommended={result.recommended_branch}"


def _composition_artifact(root: Path, scene_path: Path, agent_tasks: bool) -> tuple[dict[str, str], str]:
    result = build_scene_composition(root, scene=scene_path, rebuild_context=False, agent_tasks=agent_tasks)
    artifacts = {
        "scene_composition": _rel_str(result.output_path, root),
        "scene_composition_json": _rel_str(result.json_path, root),
        "context_trace": _rel_str(result.context_trace_path, root),
    }
    if result.agent_tasks_path:
        artifacts["scene_composition_agent_tasks"] = _rel_str(result.agent_tasks_path, root)
    return artifacts, f"branch={result.selected_branch}; beats={result.beat_count}; characters={result.character_count}"


def _generation_artifact(root: Path, scene_path: Path, provider: str, agent_tasks: bool) -> tuple[dict[str, str], str]:
    scene_id = scene_path.stem
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    if not context_path.exists():
        context_path = build_context_packet(root, scene=scene_path, rebuild_index=True).output_path
    prompt_pack = build_scene_prompt_pack(root, scene_path, context_path)
    candidate_path = root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
    prompt_manifest_path = candidate_path.with_suffix(".prompt.json")
    write_prompt_manifest(prompt_pack, prompt_manifest_path, provider="platform-agent", model="tool-layer-agent")
    result = write_platform_scene_generation_task(
        root,
        scene_path=scene_path,
        context_path=context_path,
        composition_path=prompt_pack.composition_path,
        prompt_manifest_path=prompt_manifest_path,
        candidate_path=candidate_path,
    )
    candidate_task = _rel_str(result.task_path, root)
    artifacts = {
        "candidate_task": candidate_task,
        "candidate_agent_tasks": candidate_task,
        "context_trace": _rel_str(prompt_pack.context_trace_path, root),
        "expected_candidate": _rel_str(result.expected_report_path, root),
        "expected_candidate_manifest": _rel_str(result.expected_json_path, root),
        "prompt_manifest": _rel_str(prompt_manifest_path, root),
    }
    if result.expected_report_path.exists():
        artifacts["candidate"] = _rel_str(result.expected_report_path, root)
    return artifacts, "platform-agent generation task written; no local provider invoked"


def _asset_candidate_artifact(root: Path, asset_type: str, provider: str, brief: str) -> tuple[dict[str, str], str]:
    result = write_platform_asset_creation_task(root, asset_type=asset_type, brief=brief)
    key = asset_type.replace("-", "_")
    return {
        f"{key}_candidate_task": _rel_str(result.task_path, root),
        f"{key}_candidate_expected": _rel_str(result.expected_json_path, root),
        f"{key}_candidate_report_expected": _rel_str(result.expected_report_path, root),
    }, "platform-agent asset creation task written; no local provider invoked"


def _asset_review_artifact(root: Path, candidate: str, provider: str) -> tuple[dict[str, str], str]:
    candidate_path = Path(candidate)
    result = write_platform_asset_review_task(root, candidate_path=candidate_path)
    key = candidate_path.stem.replace("-", "_")
    return {
        f"{key}_asset_review_task": _rel_str(result.task_path, root),
        f"{key}_asset_review_expected_report": _rel_str(result.expected_report_path, root),
        f"{key}_asset_review_expected_json": _rel_str(result.expected_json_path, root),
    }, "platform-agent asset review task written; no local provider invoked"


def _promotion_artifact(root: Path, scene_path: Path, candidate: str, overwrite: bool) -> tuple[dict[str, str], str]:
    candidate_path = Path(candidate) if candidate else None
    result = promote_scene_candidate(root, scene=scene_path, candidate=candidate_path, overwrite=overwrite)
    return {
        "promoted_draft": _rel_str(result.draft_path, root),
        "promotion_manifest": _rel_str(result.manifest_path, root),
        "promotion_report": _rel_str(result.report_path, root),
    }, f"candidate={_rel_str(result.candidate_path, root)}; chars={result.chars}"


def _draft_artifact(root: Path, scene_path: Path) -> tuple[dict[str, str], str]:
    result = build_scene_draft(root, scene=scene_path, rebuild_context=False)
    return {"draft": _rel_str(result.draft_path, root)}, "draft workspace generated"


def _review_artifact(root: Path, draft_path: Path) -> tuple[dict[str, str], str]:
    result = review_scene_draft(root, draft_path)
    message = f"conclusion={result.conclusion}; issues={result.issue_count}"
    return {"review": _rel_str(result.report_path, root), "review_conclusion": result.conclusion}, message


def _agent_scene_review_artifact(root: Path, scene_path: Path, draft_path: Path, provider: str) -> tuple[dict[str, str], str]:
    result = write_platform_scene_review_task(root, scene_path=scene_path, draft_path=draft_path)
    return {
        "agent_scene_review_task": _rel_str(result.task_path, root),
        "agent_scene_review_expected_report": _rel_str(result.expected_report_path, root),
        "agent_scene_review_expected_json": _rel_str(result.expected_json_path, root),
    }, "platform-agent task written; no local provider invoked"


def _agent_canon_review_artifact(root: Path, provider: str) -> tuple[dict[str, str], str]:
    result = write_platform_canon_review_task(root)
    return {
        "agent_canon_review_task": _rel_str(result.task_path, root),
        "agent_canon_review_expected_report": _rel_str(result.expected_report_path, root),
        "agent_canon_review_expected_json": _rel_str(result.expected_json_path, root),
    }, "platform-agent task written; no local provider invoked"


def _agent_committee_artifact(root: Path, scene_id: str, draft_path: Path, provider: str) -> tuple[dict[str, str], str]:
    result = write_platform_committee_task(root, subject=f"scene-{scene_id}", source=draft_path)
    return {
        "agent_committee_task": _rel_str(result.task_path, root),
        "agent_committee_expected_report": _rel_str(result.expected_report_path, root),
        "agent_committee_expected_json": _rel_str(result.expected_json_path, root),
    }, "platform-agent task written; no local provider invoked"


def _state_patch_artifact(root: Path, scene_path: Path, source_path: Path, agent_tasks: bool) -> tuple[dict[str, str], str]:
    result = build_character_state_patch(root, scene=scene_path, source=source_path, agent_tasks=agent_tasks)
    artifacts = {
        "state_patch": _rel_str(result.output_path, root),
        "state_patch_json": _rel_str(result.json_path, root),
    }
    if result.agent_tasks_path:
        artifacts["state_patch_agent_tasks"] = _rel_str(result.agent_tasks_path, root)
    return artifacts, f"characters={result.character_count}; unresolved={result.unresolved_count}"


def _chapter_artifact(root: Path, chapter_id: str, agent_review: bool) -> tuple[dict[str, str], str]:
    result = build_chapter_workspace(root, chapter_id=chapter_id, build_missing=False, review_drafts=False, agent_review=agent_review)
    message = f"scenes={result.scene_count}; ready={result.ready_count}; blocked={result.blocked_count}"
    return {"chapter_workspace": _rel_str(result.markdown_path, root), "chapter_state": _rel_str(result.json_path, root)}, message


def _longform_artifact(root: Path, target_length: int) -> tuple[dict[str, str], str]:
    result = build_longform_audit(root, target_length=target_length)
    message = f"scenes={result.scene_count}; issues={result.issue_count}; draft_chars={result.draft_chars}"
    return {"longform_audit": _rel_str(result.markdown_path, root), "longform_graph": _rel_str(result.graph_path, root)}, message


def _export_artifact(root: Path, chapter_id: str, include_blocked: bool) -> tuple[dict[str, str], str]:
    result = build_export_package(root, chapter_id=chapter_id, include_blocked=include_blocked)
    message = f"exported={result.exported_scene_count}; skipped={result.skipped_scene_count}"
    return {
        "export_manifest": _rel_str(result.manifest_path, root),
        "novel_export": _rel_str(result.novel_path, root),
        "screenplay_export": _rel_str(result.screenplay_path, root),
        "video_prompt_pack": _rel_str(result.video_prompt_path, root),
    }, message


def _final_status(state: WorkflowState) -> str:
    if any(event.status == "failed" for event in state.events):
        return "failed"
    if any(event.status == "blocked" for event in state.events):
        state.human_approval_required = True
        return "blocked"
    review_conclusion = state.artifacts.get("review_conclusion", "")
    if review_conclusion in {"reject", "revise_required"}:
        state.human_approval_required = True
        state.warnings.append(f"review not passed: {review_conclusion}")
        return "blocked"
    if any("skipped" == event.status for event in state.events):
        state.human_approval_required = True
        return "completed_with_skips"
    return "completed"


def _state_json(state: WorkflowState) -> str:
    data = asdict(state)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _render_log(state: WorkflowState) -> str:
    lines = [
        f"# Workflow Run：{state.run_id}",
        "",
        f"- 模式：`{state.mode}`",
        f"- 状态：`{state.status}`",
        f"- 项目：`{state.project_root}`",
        f"- 场景：`{state.scene or 'n/a'}`",
        f"- 章节：`{state.chapter_id}`",
        f"- 开始：{state.started_at}",
        f"- 结束：{state.ended_at}",
        f"- 恢复来源：`{state.resumed_from or 'n/a'}`",
        f"- 需要人工确认：{str(state.human_approval_required).lower()}",
        "",
        "## 节点日志",
        "",
        "| 节点 | 状态 | 信息 |",
        "| --- | --- | --- |",
    ]
    for event in state.events:
        lines.append(f"| `{event.node_id}` | {event.status} | {event.message or ''} |")
    lines.extend(["", "## 产物", ""])
    if state.artifacts:
        for key, value in state.artifacts.items():
            lines.append(f"- `{key}`：`{value}`")
    else:
        lines.append("- 无。")
    if state.warnings:
        lines.extend(["", "## 警告", ""])
        for warning in state.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _resolve_scene(root: Path, scene: Path | None) -> Path:
    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    return scene_path.resolve()


def _project_brief(root: Path) -> str:
    path = root / "project.yaml"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = []
    for key in ["title", "premise", "genre", "central_question"]:
        match = re.search(rf"{key}:\s*(.+)", text)
        if match:
            lines.append(f"{key}: {match.group(1).strip()}")
    return "\n".join(lines)


def _resolve_output_dir(root: Path, output_dir: Path | None, run_id: str) -> Path:
    if output_dir is None:
        return root / "workflow" / "runs" / run_id
    return output_dir if output_dir.is_absolute() else root / output_dir


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _validate_run_id(value: str | None) -> str:
    run_id = (value or "").strip()
    if not run_id:
        raise ValueError("run_id must not be empty")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id) or ".." in run_id:
        raise ValueError("run_id may contain only letters, numbers, dot, underscore, and hyphen")
    return run_id


def _require_existing_run(root: Path, run_id: str) -> None:
    state_path = root / "workflow" / "runs" / run_id / "workflow_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"cannot resume missing workflow run: {run_id}")


def _append_run_index(root: Path, state: WorkflowState, state_path: Path, log_path: Path) -> None:
    index_path = root / "workflow" / "runs" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "literary-engineering-workbench/workflow-run-index/v0.1",
        "run_id": state.run_id,
        "mode": state.mode,
        "status": state.status,
        "scene": state.scene,
        "chapter_id": state.chapter_id,
        "started_at": state.started_at,
        "ended_at": state.ended_at,
        "human_approval_required": state.human_approval_required,
        "resumed_from": state.resumed_from,
        "state_path": _rel_str(state_path, root),
        "log_path": _rel_str(log_path, root),
    }
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _artifact_exists(root: Path, value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    resolved = path if path.is_absolute() else root / path
    return resolved.exists()
