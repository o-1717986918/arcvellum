"""Scene composition packet builder.

This module turns context, character BDI/background, and branch simulation
artifacts into a deterministic writing plan for one scene.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....agent_tasks import default_agent_tasks_path, write_agent_tasks
from ....context_broker import context_trace_status, default_context_trace_path
from ....context_packet import build_context_packet
from ....creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    render_creative_quality_prompt,
)
from ....flow_gates import (
    FlowGateError,
    ensure_agent_task_completed,
)
from ....narrative_rhythm import narrative_rhythm_contract
from ....reader_experience import reader_experience_contract
from ....roleplay_lab import CharacterCard, _load_characters
from ....semantic_task_contracts import (
    semantic_artifact_relative_path,
    write_semantic_artifact_template,
)
from ....word_budget import scene_word_budget_contract
from ...style.snapshot import (
    active_style_mount_snapshot_bytes,
    active_style_mount_snapshot_payload,
)
from ..facts import SceneFacts, load_scene_facts
from .beats import build_beats as _build_beats, composition_obligations
from .branch_choice import fallback_writeback, load_branch_choice
from .contracts import SceneCompositionResult, SceneCompositionSources
from .creative_plan import (
    build_dialogue_intents,
    build_prose_seed,
    build_sensory_palette,
    build_subtext_map,
    character_payload,
    flow_gate,
    guardrails,
    revision_targets,
    serializable_branch,
)
from .execution_contract import build_prose_execution_contract
from .rendering import render_composition_report

# Compatibility name retained for existing extension/tests; implementation is
# owned by branch_choice.
_load_branch_choice = load_branch_choice


def build_scene_composition(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    branch_manifest: Path | None = None,
    branch_selection: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks: bool = False,
    allow_recommended_branch: bool = False,
    allow_missing_branch: bool = False,
) -> SceneCompositionResult:
    """Build a scene composition packet and JSON manifest."""

    sources = _prepare_sources(
        project_root,
        scene,
        context,
        query=query,
        rebuild_context=rebuild_context,
        branch_manifest=branch_manifest,
        branch_selection=branch_selection,
        agent_tasks=agent_tasks,
        allow_recommended_branch=allow_recommended_branch,
        allow_missing_branch=allow_missing_branch,
    )
    payload = _composition_payload(sources, agent_tasks=agent_tasks)
    _attach_prose_execution_contract(payload, allow_incomplete=allow_missing_branch)
    output_path, json_path = _composition_paths(sources, output, json_output)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(
        render_composition_report(
            sources.root,
            sources.scene_path,
            sources.context_path,
            sources.context_trace_path,
            payload,
        ),
        encoding="utf-8",
    )
    agent_tasks_path = None
    if agent_tasks:
        write_semantic_artifact_template(
            sources.root,
            "composition-agent-task",
            sources.facts.scene_id,
            source=json_path.relative_to(sources.root).as_posix(),
            # Preserve a completed review until the changed composition digest
            # makes it stale. Rebuilding must not erase reviewer evidence.
            overwrite=False,
        )
        agent_tasks_path = _write_composition_agent_tasks(
            sources.root,
            sources.scene_path,
            sources.context_path,
            sources.context_trace_path,
            output_path,
            json_path,
            payload,
        )

    return SceneCompositionResult(
        project_root=sources.root,
        output_path=output_path,
        json_path=json_path,
        agent_tasks_path=agent_tasks_path,
        context_path=sources.context_path,
        context_trace_path=sources.context_trace_path,
        scene_id=sources.facts.scene_id,
        selected_branch=str(sources.branch["branch_id"] or "none"),
        character_count=len(sources.writing_cards),
        beat_count=len(payload["beats"]),
    )


def _prepare_sources(
    project_root: Path,
    scene: Path | None,
    context: Path | None,
    *,
    query: str,
    rebuild_context: bool,
    branch_manifest: Path | None,
    branch_selection: Path | None,
    agent_tasks: bool,
    allow_recommended_branch: bool,
    allow_missing_branch: bool,
) -> SceneCompositionSources:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = _resolve(root, scene, root / "scenes" / "scene_0001.yaml")
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    facts = load_scene_facts(scene_path)
    context_path = _resolve(
        root,
        context,
        root / "memory" / "context_packets" / f"{facts.scene_id}.md",
    )
    context_path, trace_path = _ensure_context(
        root, scene_path, facts, context_path, query, rebuild_context
    )
    if agent_tasks and not allow_missing_branch:
        ensure_agent_task_completed(
            root,
            root / "branches" / facts.scene_id / "branch_manifest.agent_tasks.md",
            label="compose-scene --agent-tasks",
        )
    cards = _load_characters(root)
    return SceneCompositionSources(
        root=root,
        scene_path=scene_path,
        facts=facts,
        context_path=context_path,
        context_trace_path=trace_path,
        all_cards=cards,
        active_cards=_active_cards(cards, facts.participants),
        branch=load_branch_choice(
            root,
            facts.scene_id,
            branch_manifest,
            branch_selection,
            allow_recommended_branch,
            allow_missing_branch,
        ),
    )


def _ensure_context(
    root: Path,
    scene_path: Path,
    facts: SceneFacts,
    context_path: Path,
    query: str,
    rebuild_context: bool,
) -> tuple[Path, Path]:
    trace_path = default_context_trace_path(context_path)
    if not (
        rebuild_context
        or not context_path.exists()
        or not trace_path.exists()
        or not context_trace_status(root, facts.scene_id, context_path).passed
    ):
        return context_path, trace_path
    result = build_context_packet(
        root,
        scene=scene_path,
        query=query,
        rebuild_index=True,
        output=context_path,
    )
    rebuilt = result.output_path
    return rebuilt, result.trace_path or default_context_trace_path(rebuilt)


def _composition_payload(
    sources: SceneCompositionSources,
    *,
    agent_tasks: bool,
) -> dict[str, Any]:
    facts = sources.facts
    branch = sources.branch
    cards = sources.writing_cards
    sensory = build_sensory_palette(facts, branch)
    word_contract = scene_word_budget_contract(sources.root, sources.scene_path)
    reader_contract = reader_experience_contract(sources.root, sources.scene_path)
    rhythm_contract = narrative_rhythm_contract(sources.root, sources.scene_path)
    beats = _build_beats(facts, sources.active_cards, branch)
    quality_profile = load_creative_quality_profile(sources.root)
    return {
        "schema": "literary-engineering-workbench/scene-composition/v0.1",
        "generated_at": _now(),
        "project_root": str(sources.root),
        "formal_cli_provenance": _provenance(sources, agent_tasks),
        "scene_id": facts.scene_id,
        "scene_file": _rel(sources.scene_path, sources.root),
        "context_packet": _rel(sources.context_path, sources.root),
        "context_trace": _rel(sources.context_trace_path, sources.root),
        "branch_manifest": _branch_path(branch, "manifest_path", sources.root),
        "branch_selection": _branch_path(branch, "selection_path", sources.root),
        "selected_branch": branch["branch_id"],
        "selection_source": branch["source"],
        "flow_gate": flow_gate(branch),
        "scene_facts": asdict(facts),
        "characters": [character_payload(card, sources.root) for card in cards],
        "branch": serializable_branch(branch, sources.root),
        "beats": beats,
        "composition_obligations": composition_obligations(
            facts, branch, rhythm_contract, word_contract
        ),
        "subtext_map": build_subtext_map(facts, cards),
        "dialogue_intents": build_dialogue_intents(facts, cards),
        "sensory_palette": sensory,
        "prose_seed": build_prose_seed(facts, cards, branch, sensory),
        "word_budget_contract": word_contract,
        "reader_experience_contract": reader_contract,
        "narrative_rhythm_contract": rhythm_contract,
        "narrative_rhythm": rhythm_contract.get("narrative_rhythm", {}),
        "scene_bridge": rhythm_contract.get("scene_bridge", {}),
        "creative_quality_profile": quality_profile,
        "creative_quality_profile_digest": quality_profile.get("digest"),
        "style_mount_snapshot": active_style_mount_snapshot_payload(sources.root),
        "revision_targets": revision_targets(facts, sources.active_cards, branch),
        "writeback_candidates": branch.get(
            "writeback_candidates", fallback_writeback(facts)
        ),
        "guardrails": guardrails(),
    }


def _provenance(
    sources: SceneCompositionSources,
    agent_tasks: bool,
) -> dict[str, Any]:
    return {
        "created_by": "compose-scene",
        "agent_tasks_requested": bool(agent_tasks),
        "semantic_review_required": bool(agent_tasks),
        "manual_file_creation_allowed": False,
        "input_contract_digest": composition_input_digest(
            sources.root, sources.scene_path
        ),
        "required_predecessors": [
            "context",
            "simulate-scene --agent",
            "branch-simulate --agent",
            "branch_selection.md decision:selected",
        ],
    }


def _branch_path(branch: dict[str, Any], key: str, root: Path) -> str:
    path = branch.get(key)
    return _rel(path, root) if isinstance(path, Path) else ""


def _composition_paths(
    sources: SceneCompositionSources,
    output: Path | None,
    json_output: Path | None,
) -> tuple[Path, Path]:
    default = sources.root / "drafts" / "compositions"
    paths = (
        _resolve(
            sources.root,
            output,
            default / f"{sources.facts.scene_id}_composition.md",
        ),
        _resolve(
            sources.root,
            json_output,
            default / f"{sources.facts.scene_id}_composition.json",
        ),
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def composition_input_digest(project_root: Path, scene_path: Path) -> str:
    """Digest the formal inputs that make a composition safe to reuse."""

    root = project_root.resolve()
    scene = scene_path if scene_path.is_absolute() else root / scene_path
    facts = load_scene_facts(scene)
    input_paths = [
        scene,
        root / "project.yaml",
        root / "memory" / "context_packets" / f"{facts.scene_id}.md",
        root / "memory" / "context_packets" / f"{facts.scene_id}.trace.json",
        root / "branches" / facts.scene_id / "branch_manifest.json",
        root / semantic_artifact_relative_path("branch-agent-task", facts.scene_id),
        root / "branches" / facts.scene_id / "branch_selection.md",
        root / "plot" / "word_budget" / "word_budget.json",
        root / "plot" / "chapter_obligations" / f"{facts.chapter_id}.json",
        root / "plot" / "rhythm_plan.json",
        creative_quality_profile_path(root),
    ]
    digest = hashlib.sha256()
    for path in input_paths:
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            relative = str(path)
        digest.update(relative.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
    digest.update(active_style_mount_snapshot_bytes(root))
    return digest.hexdigest()


def _write_composition_agent_tasks(
    root: Path,
    scene_path: Path,
    context_path: Path,
    context_trace_path: Path,
    output_path: Path,
    json_path: Path,
    payload: dict[str, Any],
) -> Path:
    source_paths = [scene_path, context_path, context_trace_path, output_path, json_path]
    branch_manifest = str(payload.get("branch_manifest") or "")
    branch_selection = str(payload.get("branch_selection") or "")
    if branch_manifest:
        source_paths.append(root / branch_manifest)
    if branch_selection:
        source_paths.append(root / branch_selection)
    reader_contract = payload.get("reader_experience_contract") if isinstance(payload.get("reader_experience_contract"), dict) else {}
    chapter_contract = reader_contract.get("chapter_obligation") if isinstance(reader_contract.get("chapter_obligation"), dict) else {}
    obligation_path = str(chapter_contract.get("path") or "")
    if obligation_path:
        source_paths.append(root / obligation_path)
    if creative_quality_profile_exists(root):
        source_paths.append(creative_quality_profile_path(root))
    quality_profile = load_creative_quality_profile(root)
    quality_prompt = render_creative_quality_prompt(quality_profile, scope=str(payload["scene_id"]))
    review_rel = semantic_artifact_relative_path("composition-agent-task", str(payload["scene_id"]))
    source_paths.append(root / review_rel)
    return write_agent_tasks(
        default_agent_tasks_path(output_path),
        title=f"compose-scene {payload['scene_id']}",
        root=root,
        source_paths=source_paths,
        notes=[
            "composition.md 可能进入 generate-scene 的 prompt pack，因此不要把 AGENT_TASK 写回 composition.md。",
            "composition.json 是机器契约，不能写入 AGENT_TASK 标记。",
            f"正式审查结论必须写入 `{review_rel}`；仅完成 sidecar marker 不构成可进入正文生成的编排审查。",
        ],
        tasks=[
            (
                "审查场景编排",
                f"""读取 composition.md 与 composition.json，检查 selected_branch、selection_source、flow_gate、beats、composition_obligations、subtext_map、dialogue_intents、sensory_palette 和 prose_seed 是否互相一致。Agent 分支可使用 2-8 个可变节拍，固定 fallback 才默认五拍；无论数量多少都必须覆盖 goal、turn、incoming_bridge、outgoing_hook、cost、reader_effect，并服从权威 word_target_hanzi。selection_source 必须是 selection 才能进入 generate-scene；否则先补 branch_selection.md 或重跑 branch-simulate。把每条发现写进 `{review_rel}` 的 findings。""",
            ),
            (
                "检查人物隐性动因",
                """逐个角色检查 background_story 是否只作为选择、回避、误判、语气和关系压力的隐性因果存在。标出任何可能把背景故事写成直白说明段落的 prose_seed 或 dialogue intent。""",
            ),
            (
                "检查进入生成条件",
                f"""判断当前 composition 是否适合作为 generate-scene 的输入。若适合，列出必须传给正文生成的硬约束；若不适合，提出最小修订步骤。硬约束必须包括场景字数预算口径、章节义务、读者问题、承诺回报、暂扣信息、兑现/延迟、反摘要要求，以及 Creative Quality Profile digest `{quality_profile.get('digest')}`。不得凭记忆改写或缩短品质档案。写入 `{review_rel}`：source_artifact={json_path.relative_to(root).as_posix()}、composition_sha256（精确 SHA-256）、evidence_paths、verdict、required_changes；只有 verdict=pass 且 ready_for_generation=true 时可写 status=complete。""",
            ),
            (
                "执行创作品质档案",
                f"""以下规则不是事后审查备注，而是本场正文生成前的正式约束。逐项确认 composition 的 beats、prose_seed、dialogue_intents 与它们没有冲突；若文风挂载要求例外，必须先登记显式例外，不能自行放宽。\n\n{quality_prompt}""",
            ),
            (
                "检查读者体验与章节义务",
                """读取 reader_experience_contract 与 chapter_obligation。确认本场不是只有事件摘要，而是有明确读者问题、期待回报、张力来源、信息暂扣、兑现或延迟、情绪曲线和读后余味。若契约缺失或 incomplete，停止进入正文生成，先运行 chapter-obligation 并完成平台 Agent 侧车。""",
            ),
            (
                "检查叙事节奏与场景桥接",
                """读取 narrative_rhythm_contract、narrative_rhythm 和 scene_bridge。必须为 tension_curve 填写 entry / peak / exit 三个 1-5 整数，并说明张力如何由入场经过本场选择升降到出场；不能只写“先慢后快”。确认本场开头接住 incoming_pressure，中段有 scene_turn，过场和高潮的详略不同，结尾留下 outgoing_hook 或 continuity_handshake。若缺失，应先补 scene.yaml 或 composition，不要把所有场景写成同一种平均节奏。""",
            ),
            (
                "检查写回候选",
                """审查 writeback_candidates，标出哪些新增事实、人物状态、关系变化和伏笔变化必须在正文和 review 后再次确认。character_changes 和 relationship_changes 只能记录本场正文会实际发生的变化；未来意图、可能变化和明确尚未落地的变化必须进入 next_scene_inputs。不要直接写入 canon 或 characters/*.yaml。""",
            ),
        ],
    )


def _active_cards(cards: list[CharacterCard], participants: list[str]) -> list[CharacterCard]:
    if not participants:
        return cards
    wanted = set(participants)
    return [card for card in cards if card.character_id in wanted or card.name in wanted]


def _attach_prose_execution_contract(payload: dict[str, Any], *, allow_incomplete: bool) -> None:
    contract = build_prose_execution_contract(payload)
    payload["prose_execution_contract"] = contract
    if contract["errors"] and not allow_incomplete:
        raise FlowGateError("composition prose execution contract is incomplete: " + "; ".join(contract["errors"]))


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
