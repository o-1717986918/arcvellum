"""Multi-branch plot simulation workbench."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_tasks import default_agent_tasks_path, write_agent_tasks
from .context_broker import default_context_trace_path
from .context_packet import build_context_packet
from .flow_gates import ensure_agent_task_completed, selected_branch_from
from .roleplay_lab import CharacterCard, _load_characters, _read


SCORE_KEYS = [
    "character_logic",
    "canon_safety",
    "dramatic_tension",
    "literary_potential",
    "longterm_payoff",
]


@dataclass(frozen=True)
class BranchCandidate:
    branch_id: str
    title: str
    strategy: str
    premise: str
    action_chain: list[str]
    character_tests: list[str]
    canon_checks: list[str]
    risks: list[str]
    writeback_candidates: dict[str, list[str]]
    scores: dict[str, int]
    total_score: int
    status: str


@dataclass(frozen=True)
class BranchSimulationResult:
    project_root: Path
    output_path: Path
    manifest_path: Path
    selection_path: Path
    agent_tasks_path: Path | None
    context_path: Path
    scene_id: str
    branch_count: int
    recommended_branch: str


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

    if branch_count < 2 or branch_count > 5:
        raise ValueError("branch_count must be between 2 and 5")

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")

    scene_text = _read(scene_path)
    scene_facts = _scene_facts(scene_path, scene_text)
    context_path = context if context and context.is_absolute() else (
        root / context if context else root / "memory" / "context_packets" / f"{scene_facts.scene_id}.md"
    )
    if rebuild_context or not context_path.exists() or not default_context_trace_path(context_path).exists():
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path
    if agent_tasks:
        ensure_agent_task_completed(
            root,
            root / "branches" / scene_facts.scene_id / "roleplay_simulation.agent_tasks.md",
            label="branch-simulate --agent",
        )

    all_cards = _load_characters(root)
    active_cards = _active_cards(all_cards, scene_facts.participants)
    candidates = _build_candidates(scene_facts, active_cards, all_cards, branch_count)
    recommended = max(candidates, key=lambda item: item.total_score).branch_id if candidates else ""

    default_dir = root / "branches" / scene_facts.scene_id
    output_path = _resolve(root, output, default_dir / "branch_simulation.md")
    manifest_path = _resolve(root, json_output, default_dir / "branch_manifest.json")
    selection_path = _resolve(root, selection_output, default_dir / "branch_selection.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/branch-simulation/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "formal_cli_provenance": {
            "created_by": "branch-simulate",
            "agent_tasks_requested": bool(agent_tasks),
            "manual_file_creation_allowed": False,
            "required_predecessors": [
                "context",
                "simulate-scene --agent",
            ],
        },
        "scene_id": scene_facts.scene_id,
        "scene_file": _rel(scene_path, root),
        "context_packet": _rel(context_path, root),
        "context_trace": _rel(default_context_trace_path(context_path), root),
        "branch_count": len(candidates),
        "recommended_branch": recommended,
        "selection_record": _rel(selection_path, root),
        "score_keys": SCORE_KEYS,
        "scene_facts": asdict(scene_facts),
        "characters": [_character_payload(card, root) for card in active_cards],
        "branches": [asdict(candidate) for candidate in candidates],
        "guardrails": [
            "分支不是 canon。",
            "推荐分支不是自动合并决定。",
            "新增事实、人物重大转折和主线分支合并必须人工确认。",
            "未通过 canon-lint 和 review 的分支不能进入正式发布。",
        ],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.write_text(_render_markdown(root, scene_path, context_path, payload), encoding="utf-8")
    if not selected_branch_from(selection_path):
        selection_path.write_text(_render_selection(scene_facts, payload), encoding="utf-8")
    agent_tasks_path = None
    if agent_tasks:
        agent_tasks_path = _write_branch_agent_tasks(root, scene_path, context_path, output_path, manifest_path, selection_path, payload)

    return BranchSimulationResult(
        project_root=root,
        output_path=output_path,
        manifest_path=manifest_path,
        selection_path=selection_path,
        agent_tasks_path=agent_tasks_path,
        context_path=context_path,
        scene_id=scene_facts.scene_id,
        branch_count=len(candidates),
        recommended_branch=recommended,
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
    return write_agent_tasks(
        default_agent_tasks_path(manifest_path),
        title=f"branch-simulate {payload['scene_id']}",
        root=root,
        source_paths=[scene_path, context_path, context_trace_path, report_path, manifest_path, selection_path],
        notes=[
            "branch_manifest.json 是机器契约，不能写入 AGENT_TASK 标记。",
            "推荐分支只是启发式建议，平台 agent 必须独立审查后再决定是否询问用户。",
        ],
        tasks=[
            (
                "审查分支候选",
                """读取 context trace、branch_simulation.md 和 branch_manifest.json，先确认分支候选使用的上下文来源完整，再逐条检查每个分支是否符合 scene_goal、participants、canon_refs、next_hooks 与人物 BDI。指出每个分支最强处、最弱处和需要补证据的地方。""",
            ),
            (
                "复核评分偏置",
                """复核每个分支的人物逻辑、Canon 安全、戏剧张力、文学潜力和长线收益评分。若启发式评分与平台 agent 的判断不同，写出修正理由。""",
            ),
            (
                "决定选择策略",
                """不要自动接受 recommended_branch。基于用户方向、人物压力和 longform 结构，决定：选择一个分支、融合多个分支、退回重做，或向用户提出一个高价值选择题。把决定写入 branch_selection.md 或作为候选审查意见提交。""",
            ),
            (
                "检查写回风险",
                """检查每个分支的 writeback_candidates，标出哪些新增事实、人物状态、关系变化和伏笔变化需要用户批准。不得直接写入 canon 或 characters/*.yaml。""",
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


def _build_candidates(
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
    branch_count: int,
) -> list[BranchCandidate]:
    archetypes = [
        ("branch_character_inevitable", "人物逻辑优先", "让角色按照当前 BDI 做最真实、最少作者操控感的选择。"),
        ("branch_conflict_escalation", "冲突升级优先", "把外部阻碍和内部矛盾同时推高，让场景产生强转折。"),
        ("branch_foreshadowing_return", "伏笔收益优先", "优先回收或加固既有伏笔，让当前场景服务长线结构。"),
        ("branch_moral_cost", "道德代价优先", "让角色为了目标付出可见代价，但不突破人物道德底线。"),
        ("branch_quiet_consequence", "余波沉淀优先", "降低表层动作，放大选择后的关系余波和主题回声。"),
    ]
    return [
        _candidate(branch_id, title, strategy, scene, active_cards, all_cards)
        for branch_id, title, strategy in archetypes[:branch_count]
    ]


def _candidate(
    branch_id: str,
    title: str,
    strategy: str,
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> BranchCandidate:
    names = _names(active_cards or all_cards)
    lead = names[0] if names else "核心角色"
    goal = scene.scene_goal or "完成当前场景目标"
    external = scene.external_conflict or "外部阻碍尚未明确"
    internal = scene.internal_conflict or "内部矛盾尚未明确"
    hook = scene.next_hooks[0] if scene.next_hooks else "为下一场景留下可追踪后果"
    foreshadow = scene.active_foreshadowing[0] if scene.active_foreshadowing else "尚未登记的潜在伏笔"
    location = scene.location or "未指定地点"

    if branch_id == "branch_character_inevitable":
        premise = f"{lead} 不选择最戏剧化的路，而选择最符合当前欲望和恐惧的路。"
        action_chain = [
            f"{lead} 先确认自己真正要达成的目标：{goal}",
            f"角色绕开便利情节，正面处理内部矛盾：{internal}",
            f"外部阻碍以低烈度但高约束的方式介入：{external}",
            f"场景结束时留下后果：{hook}",
        ]
        base = {"character_logic": 5, "canon_safety": 4, "dramatic_tension": 3, "literary_potential": 3, "longterm_payoff": 4}
    elif branch_id == "branch_conflict_escalation":
        premise = f"{location} 的外部阻碍升级，迫使 {lead} 在不完整信息下行动。"
        action_chain = [
            f"外部冲突被推到台前：{external}",
            f"{lead} 的短期行动解决一个小问题，同时制造更大的结构性麻烦。",
            f"内部矛盾被暴露：{internal}",
            "结尾留下一个必须在后续章节处理的公开后果。",
        ]
        base = {"character_logic": 3, "canon_safety": 3, "dramatic_tension": 5, "literary_potential": 4, "longterm_payoff": 4}
    elif branch_id == "branch_foreshadowing_return":
        premise = f"当前场景围绕 `{foreshadow}` 做一次轻量回收或二次埋设。"
        action_chain = [
            f"让 {lead} 注意到一个与伏笔有关的细节，而不是直接解释真相。",
            f"该细节改变角色对目标的判断：{goal}",
            "伏笔只推进一格，不在当前场景一次性说尽。",
            f"下一场景继承线索：{hook}",
        ]
        base = {"character_logic": 3, "canon_safety": 4, "dramatic_tension": 3, "literary_potential": 4, "longterm_payoff": 5}
    elif branch_id == "branch_moral_cost":
        premise = f"{lead} 可以接近目标，但必须付出关系、名誉或自我认知上的代价。"
        action_chain = [
            f"{lead} 面对目标：{goal}",
            "角色拒绝突破道德底线，但接受一个更慢、更痛的方案。",
            f"内部矛盾被压实：{internal}",
            "场景结束时生成需要人工确认的人物状态变化。",
        ]
        base = {"character_logic": 4, "canon_safety": 3, "dramatic_tension": 4, "literary_potential": 5, "longterm_payoff": 4}
    else:
        premise = f"场景不追求强反转，而让 {lead} 的选择在关系和主题层面留下余波。"
        action_chain = [
            f"保留场景目标：{goal}",
            f"让地点 `{location}` 成为情绪和关系压力的承载物。",
            "用一个克制行动替代大段解释。",
            "把后果写成可被后续审计追踪的状态变化。",
        ]
        base = {"character_logic": 4, "canon_safety": 5, "dramatic_tension": 2, "literary_potential": 4, "longterm_payoff": 3}

    risks = _risks(branch_id, scene, active_cards, all_cards)
    scores = _scores(base, scene, active_cards, all_cards)
    total = sum(scores.values())
    status = "candidate" if total >= 17 and not _blocking_context_risk(risks) else "needs_detail"
    return BranchCandidate(
        branch_id=branch_id,
        title=title,
        strategy=strategy,
        premise=premise,
        action_chain=action_chain,
        character_tests=_character_tests(active_cards, all_cards),
        canon_checks=_canon_checks(scene),
        risks=risks,
        writeback_candidates=_writeback(branch_id, scene, lead),
        scores=scores,
        total_score=total,
        status=status,
    )


def _scores(
    base: dict[str, int],
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> dict[str, int]:
    scores = dict(base)
    if not scene.scene_goal:
        scores["character_logic"] -= 1
        scores["longterm_payoff"] -= 1
    if not scene.external_conflict and not scene.internal_conflict:
        scores["dramatic_tension"] -= 1
    if not active_cards and not all_cards:
        scores["character_logic"] -= 2
        scores["literary_potential"] -= 1
    if any(_has_background_story(card) for card in active_cards or all_cards):
        scores["character_logic"] += 1
        scores["literary_potential"] += 1
    if not scene.canon_refs:
        scores["canon_safety"] -= 1
    if scene.active_foreshadowing or scene.next_hooks:
        scores["longterm_payoff"] += 1
    return {key: _clamp(scores.get(key, 1)) for key in SCORE_KEYS}


def _risks(
    branch_id: str,
    scene: SceneFacts,
    active_cards: list[CharacterCard],
    all_cards: list[CharacterCard],
) -> list[str]:
    risks: list[str] = []
    if not scene.scene_goal:
        risks.append("场景缺少 scene_goal，分支目标需要人工补齐。")
    if not scene.location:
        risks.append("场景缺少 location，世界后果判断不稳定。")
    if scene.participants and not active_cards:
        risks.append("场景 participants 未匹配正式人物档案，人物行动需要人工核对。")
    if not active_cards and not all_cards:
        risks.append("缺少正式人物档案，人物合理性评分只能作为占位。")
    if (active_cards or all_cards) and not any(_has_background_story(card) for card in active_cards or all_cards):
        risks.append("人物缺少 background_story，隐性行为因果较弱。")
    if branch_id == "branch_foreshadowing_return" and not scene.active_foreshadowing:
        risks.append("没有登记 active_foreshadowing，伏笔收益分支需要人工指定线索。")
    if not scene.canon_refs:
        risks.append("场景 input_state.canon_refs 为空，正式合并前应补 canon 引用。")
    risks.append("任何新增事实都必须进入人工确认，不得直接写入 canon。")
    return risks


def _blocking_context_risk(risks: list[str]) -> bool:
    return any(
        "缺少正式人物档案" in risk
        or "缺少 scene_goal" in risk
        or "participants 未匹配" in risk
        for risk in risks
    )


def _writeback(branch_id: str, scene: SceneFacts, lead: str) -> dict[str, list[str]]:
    label = branch_id.removeprefix("branch_")
    return {
        "new_facts": [f"{scene.scene_id} 产生 `{label}` 分支候选，等待人工决定是否进入主线。"],
        "character_changes": [f"{lead} 在 `{label}` 分支中出现可审查的行动倾向变化。"],
        "relationship_changes": ["如涉及关系变化，先写入候选，不直接覆盖人物档案。"],
        "foreshadowing_changes": [f"检查 `{label}` 是否新增、加固或回收伏笔。"],
        "next_scene_inputs": [scene.next_hooks[0] if scene.next_hooks else "为下一场景补一条明确输入状态。"],
    }


def _character_tests(active_cards: list[CharacterCard], all_cards: list[CharacterCard]) -> list[str]:
    cards = active_cards or all_cards
    if not cards:
        return ["补齐人物 BDI 后重新评估。"]
    tests = []
    for card in cards:
        tests.append(f"{card.name} 的行动必须能由 belief / desire / intention 至少两项解释。")
        if _has_background_story(card):
            tests.append(f"{card.name} 的背景故事只能通过选择、回避、误判或语气间接影响行动，不得直接讲述。")
        if card.moral_line:
            tests.append(f"{card.name} 不得无解释突破道德边界：{card.moral_line}")
    return tests


def _canon_checks(scene: SceneFacts) -> list[str]:
    checks = ["不得自动确认新增事实。", "不得改变已确认适用范围、时间线和人物关系。"]
    if scene.canon_refs:
        checks.append("逐条核对 canon refs：" + "、".join(scene.canon_refs))
    else:
        checks.append("补充 input_state.canon_refs 后再进入正稿。")
    return checks


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


def _has_background_story(card: CharacterCard) -> bool:
    return bool(card.background_summary or card.formative_events or card.behavior_influences)


def _render_markdown(root: Path, scene_path: Path, context_path: Path, payload: dict[str, object]) -> str:
    branches = payload["branches"]
    scene = payload["scene_facts"]
    lines = [
        f"# 多分支剧情推演：{payload['scene_id']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        "- 正式 CLI 来源：`branch-simulate`",
        f"- 场景文件：`{_rel(scene_path, root)}`",
        f"- 上下文包：`{_rel(context_path, root)}`",
        f"- 上下文 Trace：`{payload.get('context_trace', '')}`",
        f"- 推荐分支：`{payload['recommended_branch'] or 'n/a'}`",
        f"- 人工选择记录：`{payload['selection_record']}`",
        "",
        "## 使用规则",
        "",
        "- 分支不是 canon。",
        "- 推荐分支只代表当前启发式评分最高，不是自动合并决定。",
        "- 新事实、人物重大转折和主线分支合并必须人工确认。",
        "- 进入正稿前应继续运行 `canon-lint`、`review-scene` 或章节级审查。",
        "",
        "## 场景摘要",
        "",
        f"- 章节：`{scene['chapter_id'] or 'n/a'}`",
        f"- 地点：{scene['location'] or '未填写'}",
        f"- 参与者：{', '.join(scene['participants']) if scene['participants'] else '未填写'}",
        f"- 场景目标：{scene['scene_goal'] or '未填写'}",
        f"- 外部冲突：{scene['external_conflict'] or '未填写'}",
        f"- 内部冲突：{scene['internal_conflict'] or '未填写'}",
        "",
        "## 分支评分总览",
        "",
        "| 分支 | 状态 | 人物逻辑 | Canon 安全 | 戏剧张力 | 文学潜力 | 长线收益 | 总分 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for branch in branches:
        scores = branch["scores"]
        lines.append(
            "| `{branch_id}` {title} | {status} | {character_logic} | {canon_safety} | {dramatic_tension} | {literary_potential} | {longterm_payoff} | {total_score} |".format(
                branch_id=branch["branch_id"],
                title=_escape_pipe(branch["title"]),
                status=branch["status"],
                character_logic=scores["character_logic"],
                canon_safety=scores["canon_safety"],
                dramatic_tension=scores["dramatic_tension"],
                literary_potential=scores["literary_potential"],
                longterm_payoff=scores["longterm_payoff"],
                total_score=branch["total_score"],
            )
        )
    lines.extend(["", "## 分支候选", ""])
    for branch in branches:
        lines.extend(
            [
                f"### {branch['title']} `{branch['branch_id']}`",
                "",
                f"- 策略：{branch['strategy']}",
                f"- 前提：{branch['premise']}",
                f"- 状态：`{branch['status']}`",
                "",
                "行动链：",
                "",
                _md_list(branch["action_chain"]),
                "",
                "人物测试：",
                "",
                _md_list(branch["character_tests"]),
                "",
                "Canon 检查：",
                "",
                _md_list(branch["canon_checks"]),
                "",
                "风险：",
                "",
                _md_list(branch["risks"]),
                "",
                "写回候选：",
                "",
                _writeback_markdown(branch["writeback_candidates"]),
                "",
            ]
        )
    lines.extend(
        [
            "## 人工选择",
            "",
            "请在 `branch_selection.md` 中记录选择、理由、合并元素和必须确认的 canon 写回项。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_selection(scene: SceneFacts, payload: dict[str, object]) -> str:
    return f"""# Branch Selection：{scene.scene_id}

来源 manifest：`{payload['selection_record'].rsplit('/', 1)[0]}/branch_manifest.json`
推荐分支：`{payload['recommended_branch'] or 'n/a'}`

## 人工决定

- decision: pending
- selected_branch:
- reviewer:
- selected_at:

## 选择理由

- <!-- 填写选择理由 -->

## 合并策略

- 保留的主分支：
- 吸收的其他分支元素：
- 放弃的元素：
- 下一场景输入：

## Canon 写回确认

- 新增事实：
- 人物状态变化：
- 关系变化：
- 伏笔变化：
- 禁止自动写回项：

## 审查要求

- 合并前运行 `canon-lint`。
- 正文草稿生成后运行 `review-scene`。
- 若涉及主线方向改变，保留本选择记录作为审批证据。
"""


def _writeback_markdown(data: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for key, values in data.items():
        lines.append(f"- `{key}`")
        for value in values:
            lines.append(f"  - {value}")
    return "\n".join(lines)


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


def _names(cards: list[CharacterCard]) -> list[str]:
    return [card.name or card.character_id for card in cards]


def _md_list(items: list[str]) -> str:
    if not items:
        return "- 无。"
    return "\n".join(f"- {item}" for item in items)


def _escape_pipe(value: str) -> str:
    return str(value).replace("|", "\\|")


def _clamp(value: int) -> int:
    return max(1, min(5, value))


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
