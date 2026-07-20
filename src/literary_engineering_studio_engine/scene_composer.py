"""Scene composition packet builder.

This module turns context, character BDI/background, and branch simulation
artifacts into a deterministic writing plan for one scene.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_tasks import default_agent_tasks_path, write_agent_tasks
from .context_broker import default_context_trace_path
from .context_packet import build_context_packet
from .flow_gates import FlowGateError, branch_selection_status, ensure_agent_task_completed, selected_branch_from
from .narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from .reader_experience import reader_experience_contract
from .roleplay_lab import CharacterCard, _load_characters, _read
from .word_budget import scene_word_budget_contract


@dataclass(frozen=True)
class SceneFacts:
    scene_id: str
    chapter_id: str
    location: str
    participants: list[str]
    canon_refs: list[str]
    active_foreshadowing: list[str]
    scene_goal: str
    external_conflict: str
    internal_conflict: str
    style_constraints: list[str]
    next_hooks: list[str]


@dataclass(frozen=True)
class SceneCompositionResult:
    project_root: Path
    output_path: Path
    json_path: Path
    agent_tasks_path: Path | None
    context_path: Path
    context_trace_path: Path
    scene_id: str
    selected_branch: str
    character_count: int
    beat_count: int


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

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else _resolve(root, scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    scene_text = _read(scene_path)
    facts = _scene_facts(scene_path, scene_text)
    context_path = _resolve(
        root,
        context,
        root / "memory" / "context_packets" / f"{facts.scene_id}.md",
    )
    context_trace_path = default_context_trace_path(context_path)
    if rebuild_context or not context_path.exists() or not context_trace_path.exists():
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path
        context_trace_path = context_result.trace_path or default_context_trace_path(context_path)

    all_cards = _load_characters(root)
    active_cards = _active_cards(all_cards, facts.participants)
    if agent_tasks and not allow_missing_branch:
        ensure_agent_task_completed(
            root,
            root / "branches" / facts.scene_id / "branch_manifest.agent_tasks.md",
            label="compose-scene --agent-tasks",
        )
    branch = _load_branch_choice(root, facts.scene_id, branch_manifest, branch_selection, allow_recommended_branch, allow_missing_branch)
    beats = _build_beats(facts, active_cards, branch)
    subtext_map = _build_subtext_map(facts, active_cards or all_cards)
    dialogue_intents = _build_dialogue_intents(facts, active_cards or all_cards)
    sensory_palette = _build_sensory_palette(facts, branch)
    prose_seed = _build_prose_seed(facts, active_cards or all_cards, branch, sensory_palette)
    revision_targets = _revision_targets(facts, active_cards, branch)
    guardrails = _guardrails()
    word_budget_contract = scene_word_budget_contract(root, scene_path)
    reader_contract = reader_experience_contract(root, scene_path)
    rhythm_contract = narrative_rhythm_contract(root, scene_path)

    default_dir = root / "drafts" / "compositions"
    output_path = _resolve(root, output, default_dir / f"{facts.scene_id}_composition.md")
    json_path = _resolve(root, json_output, default_dir / f"{facts.scene_id}_composition.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    branch_payload = _serializable_branch(branch, root)
    payload: dict[str, Any] = {
        "schema": "literary-engineering-workbench/scene-composition/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "formal_cli_provenance": {
            "created_by": "compose-scene",
            "agent_tasks_requested": bool(agent_tasks),
            "manual_file_creation_allowed": False,
            "required_predecessors": [
                "context",
                "simulate-scene --agent",
                "branch-simulate --agent",
                "branch_selection.md decision:selected",
            ],
        },
        "scene_id": facts.scene_id,
        "scene_file": _rel(scene_path, root),
        "context_packet": _rel(context_path, root),
        "context_trace": _rel(context_trace_path, root),
        "branch_manifest": _rel(branch["manifest_path"], root) if branch.get("manifest_path") else "",
        "branch_selection": _rel(branch["selection_path"], root) if branch.get("selection_path") else "",
        "selected_branch": branch["branch_id"],
        "selection_source": branch["source"],
        "flow_gate": _flow_gate(branch),
        "scene_facts": asdict(facts),
        "characters": [_character_payload(card, root) for card in active_cards or all_cards],
        "branch": branch_payload,
        "beats": beats,
        "subtext_map": subtext_map,
        "dialogue_intents": dialogue_intents,
        "sensory_palette": sensory_palette,
        "prose_seed": prose_seed,
        "word_budget_contract": word_budget_contract,
        "reader_experience_contract": reader_contract,
        "narrative_rhythm_contract": rhythm_contract,
        "narrative_rhythm": rhythm_contract.get("narrative_rhythm", {}),
        "scene_bridge": rhythm_contract.get("scene_bridge", {}),
        "revision_targets": revision_targets,
        "writeback_candidates": branch.get("writeback_candidates", _fallback_writeback(facts)),
        "guardrails": guardrails,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(_render_markdown(root, scene_path, context_path, context_trace_path, payload), encoding="utf-8")
    agent_tasks_path = None
    if agent_tasks:
        agent_tasks_path = _write_composition_agent_tasks(root, scene_path, context_path, context_trace_path, output_path, json_path, payload)

    return SceneCompositionResult(
        project_root=root,
        output_path=output_path,
        json_path=json_path,
        agent_tasks_path=agent_tasks_path,
        context_path=context_path,
        context_trace_path=context_trace_path,
        scene_id=facts.scene_id,
        selected_branch=str(branch["branch_id"] or "none"),
        character_count=len(active_cards or all_cards),
        beat_count=len(beats),
    )


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
    return write_agent_tasks(
        default_agent_tasks_path(output_path),
        title=f"compose-scene {payload['scene_id']}",
        root=root,
        source_paths=source_paths,
        notes=[
            "composition.md 可能进入 generate-scene 的 prompt pack，因此不要把 AGENT_TASK 写回 composition.md。",
            "composition.json 是机器契约，不能写入 AGENT_TASK 标记。",
        ],
        tasks=[
            (
                "审查场景编排",
                """读取 composition.md 与 composition.json，检查 selected_branch、selection_source、flow_gate、beats、subtext_map、dialogue_intents、sensory_palette 和 prose_seed 是否互相一致。selection_source 必须是 selection 才能进入 generate-scene；否则先补 branch_selection.md 或重跑 branch-simulate。""",
            ),
            (
                "检查人物隐性动因",
                """逐个角色检查 background_story 是否只作为选择、回避、误判、语气和关系压力的隐性因果存在。标出任何可能把背景故事写成直白说明段落的 prose_seed 或 dialogue intent。""",
            ),
            (
                "检查进入生成条件",
                """判断当前 composition 是否适合作为 generate-scene 的输入。若适合，列出必须传给正文生成的硬约束；若不适合，提出最小修订步骤。硬约束必须包括场景字数预算口径、章节义务、读者问题、承诺回报、暂扣信息、兑现/延迟和反摘要要求。""",
            ),
            (
                "检查读者体验与章节义务",
                """读取 reader_experience_contract 与 chapter_obligation。确认本场不是只有事件摘要，而是有明确读者问题、期待回报、张力来源、信息暂扣、兑现或延迟、情绪曲线和读后余味。若契约缺失或 incomplete，停止进入正文生成，先运行 chapter-obligation 并完成平台 Agent 侧车。""",
            ),
            (
                "检查叙事节奏与场景桥接",
                """读取 narrative_rhythm_contract、narrative_rhythm 和 scene_bridge。确认本场开头接住 incoming_pressure，中段有 scene_turn，过场和高潮的详略不同，结尾留下 outgoing_hook 或 continuity_handshake。若缺失，应先补 scene.yaml 或 composition，不要把所有场景写成同一种平均节奏。""",
            ),
            (
                "检查写回候选",
                """审查 writeback_candidates，标出哪些新增事实、人物状态、关系变化和伏笔变化必须在正文和 review 后再次确认。不要直接写入 canon 或 characters/*.yaml。""",
            ),
        ],
    )


def _scene_facts(scene_path: Path, text: str) -> SceneFacts:
    scene_id = _scalar(text, "scene_id") or scene_path.stem or "scene"
    return SceneFacts(
        scene_id=scene_id,
        chapter_id=_scalar(text, "chapter_id"),
        location=_scalar(text, "location"),
        participants=_list_value(text, "participants"),
        canon_refs=_list_value(text, "canon_refs"),
        active_foreshadowing=_list_value(text, "active_foreshadowing"),
        scene_goal=_scalar(text, "scene_goal"),
        external_conflict=_scalar(text, "external"),
        internal_conflict=_scalar(text, "internal"),
        style_constraints=_list_value(text, "style_constraints"),
        next_hooks=_list_value(text, "next_hooks"),
    )


def _load_branch_choice(
    root: Path,
    scene_id: str,
    manifest: Path | None,
    selection: Path | None,
    allow_recommended_branch: bool,
    allow_missing_branch: bool,
) -> dict[str, Any]:
    manifest_path = _resolve(root, manifest, root / "branches" / scene_id / "branch_manifest.json")
    selection_path = _resolve(root, selection, root / "branches" / scene_id / "branch_selection.md")
    selection_gate = branch_selection_status(selection_path)
    selected = selected_branch_from(selection_path)
    if not manifest_path.exists():
        if not allow_missing_branch:
            raise FlowGateError(
                "branch simulation required before compose-scene: "
                f"missing {_rel(manifest_path, root)}. Run simulate-scene --agent, branch-simulate --agent, "
                "then record branch_selection.md before composing. For internal experiments only, pass allow_missing_branch=True or the CLI flag."
            )
        return {
            "branch_id": "",
            "title": "未加载分支",
            "strategy": "no_branch_manifest",
            "premise": "当前场景尚未生成 branch-simulate 产物，compose-scene 将使用场景目标和人物档案生成保守编排。",
            "action_chain": [],
            "scores": {},
            "status": "no_manifest",
            "source": "fallback",
            "manifest_path": manifest_path,
            "selection_path": selection_path if selection_path.exists() else None,
            "selection_gate": selection_gate,
            "risks": ["缺少 branch_manifest.json，剧情方向未经过多分支评分。"],
            "writeback_candidates": _fallback_writeback_by_id(scene_id),
        }
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    branches = data.get("branches", [])
    recommended = str(data.get("recommended_branch") or "")
    if not selected and not allow_recommended_branch:
        raise FlowGateError(
            "formal branch selection required before compose-scene: "
            f"fill {_rel(selection_path, root)} with decision: selected and selected_branch. "
            f"recommended_branch={recommended or 'n/a'} is only a scoring hint."
        )
    target_id = selected or recommended
    chosen = _find_branch(branches, target_id)
    if target_id and chosen is None:
        raise FlowGateError(
            f"selected branch {target_id} is not present in {_rel(manifest_path, root)}; "
            "rerun branch-simulate or correct branch_selection.md."
        )
    chosen = chosen or {}
    if not chosen:
        return {
            "branch_id": target_id,
            "title": "空分支清单",
            "strategy": "empty_manifest",
            "premise": "branch_manifest.json 存在，但没有可用分支。",
            "action_chain": [],
            "scores": {},
            "status": "needs_detail",
            "source": "manifest_empty",
            "manifest_path": manifest_path,
            "selection_path": selection_path if selection_path.exists() else None,
            "selection_gate": selection_gate,
            "risks": ["branch_manifest.json 无分支。"],
            "writeback_candidates": data.get("writeback_candidates", _fallback_writeback_by_id(scene_id)),
        }
    result = dict(chosen)
    result["source"] = "selection" if selected else "recommended"
    result["manifest_path"] = manifest_path
    result["selection_path"] = selection_path if selection_path.exists() else None
    result["selection_gate"] = selection_gate
    result["recommended_branch"] = recommended
    return result


def _find_branch(branches: list[Any], branch_id: str) -> dict[str, Any] | None:
    if not branch_id:
        return None
    for branch in branches:
        if isinstance(branch, dict) and branch.get("branch_id") == branch_id:
            return branch
    return None


def _build_beats(facts: SceneFacts, cards: list[CharacterCard], branch: dict[str, Any]) -> list[dict[str, str]]:
    lead = _lead_name(cards)
    location = facts.location or "未指定地点"
    goal = facts.scene_goal or "完成当前场景目标"
    external = facts.external_conflict or "外部阻碍尚未明确"
    internal = facts.internal_conflict or "内部矛盾尚未明确"
    hook = facts.next_hooks[0] if facts.next_hooks else "为下一场景留下可追踪后果"
    action_chain = [str(item) for item in branch.get("action_chain", [])]
    premise = str(branch.get("premise") or "保持人物逻辑优先。")
    moral = _first_nonempty([card.moral_line for card in cards]) or "不突破既有人物边界"

    return [
        {
            "beat_id": "beat_01",
            "function": "开场压力",
            "visible_action": f"以 `{location}` 中一个可观察异常切入，让 {lead} 在行动前先感到约束。",
            "subtext": f"不要解释背景；让 `{external}` 成为动作节奏、停顿或视线选择上的压力。",
            "craft_note": _pick(action_chain, 0, f"建立目标：{goal}"),
        },
        {
            "beat_id": "beat_02",
            "function": "接近目标",
            "visible_action": f"{lead} 采取一个低声量、可执行的动作接近目标：{goal}。",
            "subtext": f"内部矛盾 `{internal}` 通过犹豫、绕路、避开某个词或检查同伴安全体现。",
            "craft_note": _pick(action_chain, 1, premise),
        },
        {
            "beat_id": "beat_03",
            "function": "阻碍升级",
            "visible_action": f"外部阻碍推进一格，但不要让偶然性替角色做决定：{external}。",
            "subtext": "让场景压力来自已登记信息、地点规则和人物选择，不用突然降临的便利转折。",
            "craft_note": _pick(action_chain, 2, "把冲突写成行动上的具体障碍。"),
        },
        {
            "beat_id": "beat_04",
            "function": "人物选择",
            "visible_action": f"{lead} 做出一个符合当前 BDI 的选择，并保留代价。",
            "subtext": f"选择必须受 `{moral}` 约束；背景故事只能作为隐性动因，不得直白交代。",
            "craft_note": _pick(action_chain, 3, "用选择暴露人物，而不是用旁白解释人物。"),
        },
        {
            "beat_id": "beat_05",
            "function": "后果落点",
            "visible_action": f"场景结尾留下状态变化或下一场景输入：{hook}。",
            "subtext": "只确认已经写进动作的后果；新增事实保持候选状态，等待审查写回。",
            "craft_note": "结尾不要总结主题，让可追踪后果自己留下余音。",
        },
    ]


def _build_subtext_map(facts: SceneFacts, cards: list[CharacterCard]) -> list[dict[str, Any]]:
    if not cards:
        return [
            {
                "character_id": "unknown",
                "name": "未建档角色",
                "public_action": facts.scene_goal or "按场景目标行动。",
                "hidden_pressure": facts.internal_conflict or "人物隐性压力未填写。",
                "background_influence": "缺少正式人物 background_story，建议先补人物档案。",
                "do_not_write_directly": ["不要用万能旁白替代人物动机。"],
            }
        ]
    entries = []
    for card in cards:
        entries.append(
            {
                "character_id": card.character_id,
                "name": card.name,
                "public_action": _first_nonempty(card.intention) or facts.scene_goal or "完成当前场景任务。",
                "hidden_pressure": _first_nonempty(card.fear + card.secret) or facts.internal_conflict or "隐性压力未填写。",
                "background_influence": _first_nonempty(card.behavior_influences)
                or "以选择、回避、误判、语气或沉默体现过往影响。",
                "reveal_policy": card.reveal_policy or "implicit_only",
                "do_not_write_directly": [
                    "不得直白交代人物背景故事。",
                    "不得把人物心理写成设定说明书。",
                    "不得为了推进剧情让角色无解释违背 BDI。",
                ],
            }
        )
    return entries


def _build_dialogue_intents(facts: SceneFacts, cards: list[CharacterCard]) -> list[dict[str, str]]:
    if not cards:
        return [
            {
                "speaker": "未建档角色",
                "wants": facts.scene_goal or "推进场景。",
                "avoids": facts.internal_conflict or "未填写。",
                "speech_strategy": "先补人物 speech_style，再生成对白。",
                "forbidden_exposition": "不得用对白直接解释世界观和背景故事。",
            }
        ]
    intents = []
    for card in cards:
        wants = _first_nonempty(card.desire + card.intention) or facts.scene_goal or "推进当前场景目标。"
        avoids = _first_nonempty(card.fear + card.secret) or facts.internal_conflict or "避免暴露过多信息。"
        intents.append(
            {
                "speaker": card.name or card.character_id,
                "wants": wants,
                "avoids": avoids,
                "speech_strategy": card.speech_style or "让语气服务关系压力，少解释，多留白。",
                "forbidden_exposition": "不得借对白直接讲述 background_story；只能让语气、停顿和避词泄露压力。",
            }
        )
    return intents


def _build_sensory_palette(facts: SceneFacts, branch: dict[str, Any]) -> dict[str, list[str] | str]:
    motif = facts.active_foreshadowing[0] if facts.active_foreshadowing else "未登记伏笔"
    branch_title = branch.get("title") or "无分支标题"
    return {
        "location_anchor": facts.location or "未指定地点",
        "motifs": [motif, branch_title],
        "sound": _sensory_sound(facts),
        "texture": _sensory_texture(facts),
        "light": _sensory_light(facts),
        "style_filters": facts.style_constraints or ["克制", "准确", "人物行动优先"],
    }


def _build_prose_seed(
    facts: SceneFacts,
    cards: list[CharacterCard],
    branch: dict[str, Any],
    sensory: dict[str, list[str] | str],
) -> list[str]:
    lead = _lead_name(cards)
    location = facts.location or "这个地点"
    goal = facts.scene_goal or "眼前的目标"
    external = facts.external_conflict or "外部阻碍"
    hook = facts.next_hooks[0] if facts.next_hooks else "新的后果"
    premise = branch.get("premise") or "人物必须按自己的逻辑行动"
    sound = _first_nonempty(list(sensory.get("sound", []))) if isinstance(sensory.get("sound"), list) else str(sensory.get("sound", ""))
    texture = _first_nonempty(list(sensory.get("texture", []))) if isinstance(sensory.get("texture"), list) else str(sensory.get("texture", ""))

    return [
        f"{location} 先给了 {lead} 一个不肯退让的细节：{sound or '细小的动静'}。{lead} 先停住动作，确认 `{goal}` 会把局面推向哪里。",
        f"`{external}` 没有突然爆发，它只是一步一步逼近。{lead} 伸手碰到{texture or '发冷的边缘'}时，旧习惯先一步收紧了他的判断；他避开最顺手的办法，选择了更慢、更难、但仍属于他的路。",
        f"这一版正文种子采用 `{premise}` 的分支前提。结尾不要替读者总结答案，只让 `{hook}` 成为下一场景可以接住的输入。新增事实仍是候选，不能在本场景自动写入 canon。",
    ]


def _revision_targets(facts: SceneFacts, cards: list[CharacterCard], branch: dict[str, Any]) -> list[str]:
    targets = [
        "把每个节拍改写成具体动作、可观察细节和状态变化。",
        "删掉解释性背景段落，让 background_story 只通过选择、回避、误判、语气和关系压力体现。",
        "生成正文后运行 review-scene；涉及新增事实时继续运行 canon-lint。",
    ]
    if not cards and facts.participants:
        targets.append("participants 没有匹配正式人物档案，先补人物卡或修正 scene.yaml。")
    if branch.get("status") == "no_manifest":
        targets.append("建议先运行 branch-simulate，再基于评分分支重建 compose-scene。")
    if branch.get("source") != "selection":
        targets.append("当前分支未经过正式 branch_selection，不能直接进入 generate-scene。")
    if not facts.canon_refs:
        targets.append("scene.yaml 缺少 canon_refs，正稿前应补硬约束引用。")
    return targets


def _guardrails() -> list[str]:
    return [
        "composition 是写作编排，不是正稿。",
        "不得新增未经确认的 canon。",
        "不得改变人物、地点、时间线或规则的适用范围。",
        "不得把角色 background_story 直接写成说明段落。",
        "不得让分支推荐绕过人工选择、审查和发布门禁。",
        "只有 selection_source=selection 的 composition 才能进入 generate-scene；内部实验必须显式放行。",
    ]


def _flow_gate(branch: dict[str, Any]) -> dict[str, Any]:
    source = str(branch.get("source") or "")
    return {
        "branch_selection_required": True,
        "ready_for_generation": source == "selection",
        "selection_source": source,
        "selection_gate": branch.get("selection_gate", {}),
        "blocking_reason": "" if source == "selection" else "branch_selection.md has not recorded a formal selected branch",
    }


def _character_payload(card: CharacterCard, root: Path) -> dict[str, Any]:
    return {
        "file": _rel(card.file, root),
        "character_id": card.character_id,
        "name": card.name,
        "role": card.role,
        "belief": card.belief,
        "desire": card.desire,
        "intention": card.intention,
        "fear": card.fear,
        "secret": card.secret,
        "background_story": {
            "summary": card.background_summary,
            "formative_events": card.formative_events,
            "behavior_influences": card.behavior_influences,
            "reveal_policy": card.reveal_policy,
        },
        "moral_line": card.moral_line,
        "speech_style": card.speech_style,
    }


def _serializable_branch(branch: dict[str, Any], root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in branch.items():
        if isinstance(value, Path):
            result[key] = _rel(value, root)
        else:
            result[key] = value
    return result


def _render_markdown(root: Path, scene_path: Path, context_path: Path, context_trace_path: Path, payload: dict[str, Any]) -> str:
    facts = payload["scene_facts"]
    branch = payload["branch"]
    lines = [
        f"# 场景创作编排：{payload['scene_id']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景文件：`{_rel(scene_path, root)}`",
        f"- 上下文包：`{_rel(context_path, root)}`",
        f"- 上下文 Trace：`{_rel(context_trace_path, root)}`",
        f"- 选用分支：`{payload['selected_branch'] or 'none'}`（{payload['selection_source']}）",
        f"- JSON：`drafts/compositions/{payload['scene_id']}_composition.json`",
        "",
        "## 使用边界",
        "",
        _md_list(payload["guardrails"]),
        "",
        "## 输入摘要",
        "",
        f"- 章节：`{facts['chapter_id'] or 'n/a'}`",
        f"- 地点：{facts['location'] or '未填写'}",
        f"- 参与者：{', '.join(facts['participants']) if facts['participants'] else '未填写'}",
        f"- 场景目标：{facts['scene_goal'] or '未填写'}",
        f"- 外部冲突：{facts['external_conflict'] or '未填写'}",
        f"- 内部冲突：{facts['internal_conflict'] or '未填写'}",
        "",
        "## 选用分支",
        "",
        f"- 标题：{branch.get('title') or '未填写'}",
        f"- 策略：{branch.get('strategy') or '未填写'}",
        f"- 状态：`{branch.get('status') or 'n/a'}`",
        f"- 前提：{branch.get('premise') or '未填写'}",
        "",
        "行动链：",
        "",
        _md_list([str(item) for item in branch.get("action_chain", [])]),
        "",
        "## 场景节拍",
        "",
    ]
    for beat in payload["beats"]:
        lines.extend(
            [
                f"### {beat['beat_id']}：{beat['function']}",
                "",
                f"- 可见动作：{beat['visible_action']}",
                f"- 潜台词：{beat['subtext']}",
                f"- 写作提示：{beat['craft_note']}",
                "",
            ]
        )
    lines.extend(["## 人物潜台词", ""])
    for item in payload["subtext_map"]:
        lines.extend(
            [
                f"### {item['name']} `{item['character_id']}`",
                "",
                f"- 表层行动：{item['public_action']}",
                f"- 隐性压力：{item['hidden_pressure']}",
                f"- 背景影响：{item['background_influence']}",
                f"- 呈现策略：{item.get('reveal_policy', 'implicit_only')}",
                "",
                "禁止写法：",
                "",
                _md_list(item["do_not_write_directly"]),
                "",
            ]
        )
    lines.extend(["## 对白意图", ""])
    for item in payload["dialogue_intents"]:
        lines.extend(
            [
                f"- `{item['speaker']}` 想要：{item['wants']}",
                f"  避免：{item['avoids']}",
                f"  话语策略：{item['speech_strategy']}",
                f"  禁区：{item['forbidden_exposition']}",
            ]
        )
    sensory = payload["sensory_palette"]
    lines.extend(
        [
        "",
        "## 感官与意象",
        "",
            f"- 地点锚点：{sensory['location_anchor']}",
            f"- 意象：{', '.join(sensory['motifs'])}",
            f"- 声音：{', '.join(sensory['sound'])}",
            f"- 触感：{', '.join(sensory['texture'])}",
            f"- 光线：{', '.join(sensory['light'])}",
            f"- 风格过滤：{', '.join(sensory['style_filters'])}",
            "",
            "## 字数预算硬属性",
            "",
            f"- 状态：`{payload.get('word_budget_contract', {}).get('status', 'missing')}`",
            f"- 目标中文内容字符：{payload.get('word_budget_contract', {}).get('target_chinese_chars') or payload.get('word_budget_contract', {}).get('target_words', 0)}",
            f"- 最低中文内容字符：{payload.get('word_budget_contract', {}).get('min_chinese_chars') or payload.get('word_budget_contract', {}).get('min_words', 0)}",
            f"- 最高中文内容字符：{payload.get('word_budget_contract', {}).get('max_chinese_chars') or payload.get('word_budget_contract', {}).get('max_words', 0)}",
            f"- 叙事负载：{', '.join(str(item) for item in payload.get('word_budget_contract', {}).get('narrative_load', [])) or '未要求'}",
            "",
            "## 读者体验硬属性",
            "",
            f"- 状态：`{payload.get('reader_experience_contract', {}).get('status', 'missing')}`",
            f"- 信息：{payload.get('reader_experience_contract', {}).get('message', '')}",
            f"- 本场读者问题：{payload.get('reader_experience_contract', {}).get('reader_experience', {}).get('reader_question', '未填写') if isinstance(payload.get('reader_experience_contract', {}).get('reader_experience'), dict) else '未填写'}",
            f"- 承诺回报：{payload.get('reader_experience_contract', {}).get('reader_experience', {}).get('promised_reward', '未填写') if isinstance(payload.get('reader_experience_contract', {}).get('reader_experience'), dict) else '未填写'}",
            f"- 兑现或延迟：{payload.get('reader_experience_contract', {}).get('reader_experience', {}).get('payoff_or_delay', '未填写') if isinstance(payload.get('reader_experience_contract', {}).get('reader_experience'), dict) else '未填写'}",
            f"- 反摘要要求：{payload.get('reader_experience_contract', {}).get('reader_experience', {}).get('anti_summary_requirement', '未填写') if isinstance(payload.get('reader_experience_contract', {}).get('reader_experience'), dict) else '未填写'}",
            "",
            "## 叙事节奏与场景桥接硬属性",
            "",
            render_narrative_rhythm_contract(root, scene_path).strip(),
            "",
            "## 正文种子",
            "",
            "以下不是正稿，只是用于启动真实正文生成的可改写种子：",
            "",
        ]
    )
    for paragraph in payload["prose_seed"]:
        lines.extend([paragraph, ""])
    lines.extend(
        [
            "## 改写目标",
            "",
            _md_list(payload["revision_targets"]),
            "",
            "## 写回候选",
            "",
            _writeback_markdown(payload["writeback_candidates"]),
            "",
            "## 下一步",
            "",
            "- 将正文种子扩写或交给 provider 生成候选。",
            "- 把候选正文放入 `drafts/scenes/` 后运行 `review-scene`。",
            "- 通过审查和人工确认后，再进入章节工作台、导出和发布链路。",
        ]
    )
    return "\n".join(lines) + "\n"


def _active_cards(cards: list[CharacterCard], participants: list[str]) -> list[CharacterCard]:
    if not participants:
        return cards
    wanted = set(participants)
    return [card for card in cards if card.character_id in wanted or card.name in wanted]


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    value = match.group(1).strip().strip("\"'")
    return "" if value in {"", "null", "[]", "{}"} else value


def _list_value(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return []
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]
    values: list[str] = []
    base_indent = len(match.group(0)) - len(match.group(0).lstrip())
    for line in text[match.end() :].splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent <= base_indent and re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
        if stripped.startswith("-"):
            item = stripped.strip("- ").strip("\"'")
            if item:
                values.append(item)
    return values


def _sensory_sound(facts: SceneFacts) -> list[str]:
    text = " ".join([facts.location, facts.external_conflict, " ".join(facts.active_foreshadowing)])
    if "电" in text:
        return ["断续电流声", "远处脚步被空墙放大"]
    if "雨" in text:
        return ["雨点敲击硬物", "压低的呼吸声"]
    return ["低频环境声", "被刻意压住的脚步或语气"]


def _sensory_texture(facts: SceneFacts) -> list[str]:
    text = facts.location + facts.external_conflict
    if "旧" in text or "档案" in text:
        return ["纸页边缘发脆", "灰尘贴在指腹"]
    if "地下" in text:
        return ["潮湿墙面", "发凉的金属边缘"]
    return ["温度变化", "粗糙边缘", "被反复触碰的物件"]


def _sensory_light(facts: SceneFacts) -> list[str]:
    text = facts.location + facts.external_conflict
    if "停电" in text or "夜" in text:
        return ["低光", "手电余光", "门缝暗影"]
    return ["局部光源", "遮挡形成的阴影", "人物视线避开的亮处"]


def _fallback_writeback(facts: SceneFacts) -> dict[str, list[str]]:
    return {
        "new_facts": [f"{facts.scene_id} 的新增事实必须在正文生成后人工确认。"],
        "character_changes": ["人物状态变化先保持候选。"],
        "relationship_changes": ["关系变化先保持候选。"],
        "foreshadowing_changes": ["伏笔新增、加固或回收需进入审查清单。"],
        "next_scene_inputs": facts.next_hooks or ["补充下一场景输入。"],
    }


def _fallback_writeback_by_id(scene_id: str) -> dict[str, list[str]]:
    return {
        "new_facts": [f"{scene_id} 的新增事实必须在正文生成后人工确认。"],
        "character_changes": ["人物状态变化先保持候选。"],
        "relationship_changes": ["关系变化先保持候选。"],
        "foreshadowing_changes": ["伏笔新增、加固或回收需进入审查清单。"],
        "next_scene_inputs": ["补充下一场景输入。"],
    }


def _writeback_markdown(data: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for key, values in data.items():
        lines.append(f"- `{key}`")
        for value in values:
            lines.append(f"  - {value}")
    return "\n".join(lines) if lines else "- 无。"


def _md_list(items: list[str]) -> str:
    if not items:
        return "- 无。"
    return "\n".join(f"- {item}" for item in items)


def _pick(items: list[str], index: int, default: str) -> str:
    if 0 <= index < len(items) and items[index]:
        return items[index]
    return default


def _lead_name(cards: list[CharacterCard]) -> str:
    if not cards:
        return "核心角色"
    return cards[0].name or cards[0].character_id or "核心角色"


def _first_nonempty(items: list[str]) -> str:
    for item in items:
        if item:
            return item
    return ""


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
