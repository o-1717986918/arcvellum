"""Multi-branch plot simulation workbench."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ....agent_tasks import default_agent_tasks_path, write_agent_tasks
from ....context_broker import context_trace_status, default_context_trace_path
from ....context_packet import build_context_packet
from ....flow_gates import ensure_agent_task_completed, selected_branch_from
from ....roleplay_lab import CharacterCard, _load_characters
from ....semantic_task_contracts import (
    read_semantic_artifact,
    semantic_artifact_relative_path,
    write_semantic_artifact_template,
)
from ..facts import SceneFacts, load_scene_facts
from .candidates import build_fallback_candidates
from .contracts import (
    BranchBuildContext,
    BranchCandidate,
    BranchSimulationResult,
    SCORE_KEYS,
)
from .rendering import render_branch_report, render_branch_selection


def build_branch_simulation(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    branch_count: int = 4,
    output: Path | None = None,
    json_output: Path | None = None,
    selection_output: Path | None = None,
    agent_tasks: bool = False,
) -> BranchSimulationResult:
    """Create a scored branch simulation workspace for one scene."""

    build = _prepare_build_context(
        project_root,
        scene,
        context,
        query=query,
        rebuild_context=rebuild_context,
        branch_count=branch_count,
        agent_tasks=agent_tasks,
    )
    candidates = build_fallback_candidates(
        build.scene_facts,
        build.active_cards,
        build.all_cards,
        branch_count,
        build.roleplay_result,
    )
    recommended = max(candidates, key=lambda item: item.total_score).branch_id if candidates else ""
    output_path, manifest_path, selection_path = _output_paths(
        build, output, json_output, selection_output
    )
    payload = _branch_payload(build, candidates, recommended, selection_path, agent_tasks)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(
        render_branch_report(build.root, build.scene_path, build.context_path, payload),
        encoding="utf-8",
    )
    if not selected_branch_from(selection_path):
        selection_path.write_text(
            render_branch_selection(build.scene_facts, payload), encoding="utf-8"
        )
    agent_tasks_path = None
    if agent_tasks:
        agent_tasks_path = _prepare_branch_agent_task(
            build.root,
            build.scene_path,
            build.context_path,
            output_path,
            manifest_path,
            selection_path,
            payload,
        )

    return BranchSimulationResult(
        project_root=build.root,
        output_path=output_path,
        manifest_path=manifest_path,
        selection_path=selection_path,
        agent_tasks_path=agent_tasks_path,
        context_path=build.context_path,
        scene_id=build.scene_facts.scene_id,
        branch_count=len(candidates),
        recommended_branch=recommended,
    )


def _prepare_build_context(
    project_root: Path,
    scene: Path | None,
    context: Path | None,
    *,
    query: str,
    rebuild_context: bool,
    branch_count: int,
    agent_tasks: bool,
) -> BranchBuildContext:
    if branch_count < 2 or branch_count > 5:
        raise ValueError("branch_count must be between 2 and 5")
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = _scene_path(root, scene)
    scene_facts = load_scene_facts(scene_path)
    context_path = _context_path(root, context, scene_facts.scene_id)
    if _context_requires_build(root, scene_facts.scene_id, context_path, rebuild_context):
        context_path = build_context_packet(
            root,
            scene=scene_path,
            query=query,
            rebuild_index=True,
            output=context_path,
        ).output_path
    roleplay = _roleplay_result(root, scene_facts.scene_id, agent_tasks)
    all_cards = _load_characters(root)
    return BranchBuildContext(
        root=root,
        scene_path=scene_path,
        scene_facts=scene_facts,
        context_path=context_path,
        roleplay_result=roleplay,
        all_cards=all_cards,
        active_cards=_active_cards(all_cards, scene_facts.participants),
    )


def _branch_payload(
    build: BranchBuildContext,
    candidates: list[BranchCandidate],
    recommended: str,
    selection_path: Path,
    agent_tasks: bool,
) -> dict[str, object]:
    scene_id = build.scene_facts.scene_id
    return {
        "schema": "literary-engineering-workbench/branch-simulation/v0.1",
        "generated_at": _now(),
        "project_root": str(build.root),
        "formal_cli_provenance": {
            "created_by": "branch-simulate",
            "agent_tasks_requested": bool(agent_tasks),
            "manual_file_creation_allowed": False,
            "required_predecessors": ["context", "simulate-scene --agent"],
        },
        "scene_id": scene_id,
        "scene_file": _rel(build.scene_path, build.root),
        "context_packet": _rel(build.context_path, build.root),
        "context_trace": _rel(default_context_trace_path(build.context_path), build.root),
        "roleplay_result": _proposal_source(scene_id, agent_tasks),
        "roleplay_evidence": build.roleplay_result,
        "branch_count": len(candidates),
        "recommended_branch": recommended,
        "selection_record": _rel(selection_path, build.root),
        "agent_proposals": _proposal_relative(scene_id, agent_tasks),
        "score_keys": list(SCORE_KEYS),
        "scene_facts": asdict(build.scene_facts),
        "characters": [_character_payload(card, build.root) for card in build.active_cards],
        "branches": [asdict(candidate) for candidate in candidates],
        "guardrails": [
            "分支不是 canon。",
            "推荐分支不是自动合并决定。",
            "新增事实、人物重大转折和主线分支合并必须人工确认。",
            "未通过 canon-lint 和 review 的分支不能进入正式发布。",
        ],
    }


def _proposal_relative(scene_id: str, enabled: bool) -> str:
    return semantic_artifact_relative_path("branch-agent-task", scene_id) if enabled else ""


def _proposal_source(scene_id: str, enabled: bool) -> str:
    return semantic_artifact_relative_path("roleplay-agent-task", scene_id) if enabled else ""


def _scene_path(root: Path, scene: Path | None) -> Path:
    path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene, scene)
    if not path.exists():
        raise FileNotFoundError(f"scene file not found: {path}")
    return path


def _context_path(root: Path, context: Path | None, scene_id: str) -> Path:
    default = root / "memory" / "context_packets" / f"{scene_id}.md"
    return _resolve(root, context, default)


def _context_requires_build(
    root: Path,
    scene_id: str,
    context_path: Path,
    rebuild_context: bool,
) -> bool:
    return bool(
        rebuild_context
        or not context_path.exists()
        or not default_context_trace_path(context_path).exists()
        or not context_trace_status(root, scene_id, context_path).passed
    )


def _roleplay_result(
    root: Path,
    scene_id: str,
    agent_tasks: bool,
) -> dict[str, object]:
    if not agent_tasks:
        return {}
    ensure_agent_task_completed(
        root,
        root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md",
        label="branch-simulate --agent",
    )
    return read_semantic_artifact(root, "roleplay-agent-task", scene_id)


def _output_paths(
    build: BranchBuildContext,
    output: Path | None,
    json_output: Path | None,
    selection_output: Path | None,
) -> tuple[Path, Path, Path]:
    default_dir = build.root / "branches" / build.scene_facts.scene_id
    paths = (
        _resolve(build.root, output, default_dir / "branch_simulation.md"),
        _resolve(build.root, json_output, default_dir / "branch_manifest.json"),
        _resolve(build.root, selection_output, default_dir / "branch_selection.md"),
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def _prepare_branch_agent_task(
    root: Path,
    scene_path: Path,
    context_path: Path,
    output_path: Path,
    manifest_path: Path,
    selection_path: Path,
    payload: dict[str, object],
) -> Path:
    scene_id = str(payload["scene_id"])
    write_semantic_artifact_template(
        root,
        "branch-agent-task",
        scene_id,
        source=manifest_path.relative_to(root).as_posix(),
        overwrite=False,
        branch_count=int(payload["branch_count"]),
    )
    return _write_branch_agent_tasks(
        root, scene_path, context_path, output_path, manifest_path, selection_path, payload
    )


def _write_branch_agent_tasks(
    root: Path,
    scene_path: Path,
    context_path: Path,
    report_path: Path,
    manifest_path: Path,
    selection_path: Path,
    payload: dict[str, object],
) -> Path:
    context_trace_path = default_context_trace_path(context_path)
    proposal_path = root / semantic_artifact_relative_path("branch-agent-task", str(payload["scene_id"]))
    return write_agent_tasks(
        default_agent_tasks_path(manifest_path),
        title=f"branch-simulate {payload['scene_id']}",
        root=root,
        source_paths=[
            scene_path,
            context_path,
            context_trace_path,
            root / semantic_artifact_relative_path("roleplay-agent-task", str(payload["scene_id"])),
            report_path,
            manifest_path,
            proposal_path,
            selection_path,
        ],
        notes=[
            "branch_manifest.json 是机器契约，不能写入 AGENT_TASK 标记。",
            "固定五类候选只是确定性回退；正式创意判断必须写入 branch_proposals.json。",
            "推荐分支只是启发式建议，平台 agent 必须独立审查后再决定是否询问用户。",
        ],
        tasks=[
            (
                "审查分支候选",
                """读取 context trace、roleplay_result.json、branch_simulation.md 和 branch_manifest.json。固定候选只用于防止流程无路可走，不能直接换名后提交。根据本场人物行动、世界后果、分支压力、Canon 风险、scene_goal、next_hooks 与人物 BDI，提出 2-5 条场景特定分支。""",
            ),
            (
                "写入正式分支提案",
                f"""编辑已经预置精确 JSON 形状的 `{proposal_path.relative_to(root).as_posix()}`，保留顶层 schema、scene_id 和 source_artifact。把其中恰好 {payload['branch_count']} 个占位提案逐一改为真实内容；每条 `branch_id` 使用唯一 `agent_branch_<slug>`，不得改名为 id、rationale、irreversible_cost 或 next_scene_pressure。`state_writeback` 的五个字段都保持字符串列表；只有本场可见发生的变化才能写入 character_changes 或 relationship_changes，未来意图、可能变化和明确尚未落地的变化必须写入 next_scene_inputs。`beat_plan` 每拍保留 beat_id、function、visible_action、causal_change、pace、detail_level、serves，且 serves 必须是义务名称列表，整份计划覆盖 incoming_bridge、goal、turn、cost、reader_effect、outgoing_hook。不同提案必须在因果、行动链、代价、读者效果和写回上都真实不同。设置 status=complete，引用实际 evidence_paths，并在 findings 说明差异依据。""",
            ),
            (
                "决定选择策略",
                """不要自动接受 recommended_branch。优先从已验证的 Agent 提案中选择；只有提案无法成立时才使用确定性回退。基于用户方向、人物压力和 longform 结构，决定选择、融合、退回重做或提出高价值选择题，并把精确 branch_id 写入 branch_selection.md。""",
            ),
            (
                "检查写回风险",
                """检查每个提案的 state_writeback，标出哪些新增事实、人物状态、关系变化和伏笔变化需要用户批准。不得直接写入 canon 或 characters/*.yaml。""",
            ),
        ],
    )


def _active_cards(cards: list[CharacterCard], participants: list[str]) -> list[CharacterCard]:
    if not participants:
        return cards
    wanted = set(participants)
    return [card for card in cards if card.character_id in wanted or card.name in wanted]


def _character_payload(card: CharacterCard, root: Path) -> dict[str, object]:
    return {
        "file": _rel(card.file, root),
        "character_id": card.character_id,
        "name": card.name,
        "role": card.role,
        "belief": card.belief,
        "desire": card.desire,
        "intention": card.intention,
        "background_story": {
            "summary": card.background_summary,
            "formative_events": card.formative_events,
            "behavior_influences": card.behavior_influences,
            "reveal_policy": card.reveal_policy,
        },
        "moral_line": card.moral_line,
    }


def _resolve(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
