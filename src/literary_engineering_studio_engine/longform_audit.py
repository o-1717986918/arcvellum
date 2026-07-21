"""Long-form project audit and lightweight graph export."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .context_broker import context_trace_status
from .draft_text import count_delivery_chars, count_delivery_chinese_content_chars, final_body_from_draft_text
from .narrative_rhythm import analyze_narrative_rhythm_sequence, narrative_rhythm_contract
from .scene_readiness import agent_review_gate_state, scene_flow_gate_issues, scene_readiness_status
from .word_budget import load_word_budget_summary


RESOLVED_FORESHADOW_STATUSES = {
    "paid",
    "resolved",
    "closed",
    "done",
    "complete",
    "completed",
    "回收",
    "已回收",
    "完成",
    "已完成",
}


@dataclass(frozen=True)
class LongformSceneRecord:
    scene_id: str
    chapter_id: str
    scene_path: str
    location: str
    participants: tuple[str, ...]
    scene_goal: str
    draft_path: str
    review_path: str
    review_conclusion: str
    agent_review_path: str
    agent_review_json: str
    agent_review_conclusion: str
    agent_review_schema_status: str
    agent_review_source_match: bool
    agent_review_unresolved_notes: tuple[str, ...]
    style_adherence_status: str
    word_budget_adherence_status: str
    reader_experience_adherence_status: str
    reader_promise_satisfied: bool
    narrative_rhythm_status: str
    rhythm_role: str
    pace: str
    tension_curve: object
    scene_function: tuple[str, ...]
    scene_turn: str
    reader_effect: str
    incoming_pressure: str
    outgoing_hook: str
    flow_gate_issues: tuple[str, ...]
    readiness_issues: tuple[str, ...]
    draft_chars: int
    draft_machine_chars: int
    status: str


@dataclass(frozen=True)
class LongformIssue:
    severity: str
    category: str
    subject: str
    message: str
    recommendation: str


@dataclass(frozen=True)
class LongformAuditResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    graph_path: Path
    scene_count: int
    chapter_count: int
    issue_count: int
    draft_chars: int


def build_longform_audit(
    project_root: Path,
    target_length: int = 100000,
    output: Path | None = None,
    json_output: Path | None = None,
    graph_output: Path | None = None,
) -> LongformAuditResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    scenes = _scan_scenes(root)
    characters = _scan_characters(root)
    foreshadowing = _scan_foreshadowing(root)
    chapter_files = sorted((root / "plot" / "chapters").glob("*.json")) if (root / "plot" / "chapters").exists() else []
    word_budget = load_word_budget_summary(root)
    rhythm_curves = _rhythm_curves(scenes)
    issues = _audit_issues(root, scenes, characters, foreshadowing, chapter_files, target_length, word_budget)
    issues.extend(_rhythm_curve_issues(rhythm_curves))
    graph = _build_graph(scenes, characters, foreshadowing)

    markdown_path = _resolve_output(root, output, "reviews", "longform", "longform_audit.md")
    json_path = _resolve_output(root, json_output, "reviews", "longform", "longform_audit.json")
    graph_path = _resolve_output(root, graph_output, "plot", "longform_graph.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.parent.mkdir(parents=True, exist_ok=True)

    summary = _summary(scenes, characters, foreshadowing, chapter_files, issues, target_length, word_budget)
    payload = {
        "schema": "literary-engineering-workbench/longform-audit/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "summary": summary,
        "word_budget": word_budget,
        "rhythm_curves": rhythm_curves,
        "scenes": [asdict(scene) for scene in scenes],
        "characters": characters,
        "foreshadowing": foreshadowing,
        "issues": [asdict(issue) for issue in issues],
        "graph_path": _rel_str(graph_path, root),
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(root, payload, graph_path), encoding="utf-8")

    return LongformAuditResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        graph_path=graph_path,
        scene_count=len(scenes),
        chapter_count=summary["chapter_count"],
        issue_count=len(issues),
        draft_chars=summary["draft_chars"],
    )


def _scan_scenes(root: Path) -> list[LongformSceneRecord]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    records = []
    for scene_path in sorted(scene_dir.glob("*.yaml")):
        if scene_path.name.startswith("_"):
            continue
        text = _read(scene_path)
        scene_id = _scalar(text, "scene_id") or scene_path.stem
        draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"
        review_path = root / "reviews" / f"{scene_id}-review.md"
        agent_review_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.md"
        agent_review_json_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
        composition_json_path = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
        draft_text = _read(draft_path)
        body = final_body_from_draft_text(draft_text) if draft_text else ""
        review_text = _read(review_path)
        conclusion = _review_conclusion(review_text)
        flow_issues = scene_flow_gate_issues(root, scene_id)
        agent_state = agent_review_gate_state(root, agent_review_json_path, draft_path)
        status, readiness_issues = scene_readiness_status(
            root,
            draft_path=draft_path,
            review_path=review_path,
            agent_review_json_path=agent_review_json_path,
            body=body,
            static_review_conclusion=conclusion,
            flow_gate_issues=flow_issues,
            agent_review_state=agent_state,
        )
        rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_json_path)
        rhythm_payload = rhythm_contract.get("narrative_rhythm") if isinstance(rhythm_contract.get("narrative_rhythm"), dict) else {}
        bridge_payload = rhythm_contract.get("scene_bridge") if isinstance(rhythm_contract.get("scene_bridge"), dict) else {}
        records.append(
            LongformSceneRecord(
                scene_id=scene_id,
                chapter_id=_scalar(text, "chapter_id") or "unassigned",
                scene_path=_rel_str(scene_path, root),
                location=_scalar(text, "location"),
                participants=tuple(_list_after(text, "participants")),
                scene_goal=_scalar(text, "scene_goal"),
                draft_path=_existing_rel(draft_path, root),
                review_path=_existing_rel(review_path, root),
                review_conclusion=conclusion,
                agent_review_path=_existing_rel(agent_review_path, root),
                agent_review_json=_existing_rel(agent_review_json_path, root),
                agent_review_conclusion=str(agent_state.get("conclusion") or ""),
                agent_review_schema_status=str(agent_state.get("schema_status") or ""),
                agent_review_source_match=bool(agent_state.get("source_match")),
                agent_review_unresolved_notes=tuple(str(item) for item in agent_state.get("unresolved_notes", [])),
                style_adherence_status=str(agent_state.get("style_adherence_status") or ""),
                word_budget_adherence_status=str(agent_state.get("word_budget_adherence_status") or ""),
                reader_experience_adherence_status=str(agent_state.get("reader_experience_adherence_status") or ""),
                reader_promise_satisfied=bool(agent_state.get("reader_promise_satisfied")),
                narrative_rhythm_status=str(rhythm_contract.get("status") or ""),
                rhythm_role=str(rhythm_payload.get("rhythm_role") or ""),
                pace=str(rhythm_payload.get("pace") or ""),
                tension_curve=rhythm_payload.get("tension_curve"),
                scene_function=tuple(_string_list(rhythm_payload.get("scene_function"))),
                scene_turn=str(rhythm_payload.get("scene_turn") or ""),
                reader_effect=str(rhythm_payload.get("reader_effect") or ""),
                incoming_pressure=str(bridge_payload.get("incoming_pressure") or ""),
                outgoing_hook=_outgoing_hook_text(bridge_payload),
                flow_gate_issues=flow_issues,
                readiness_issues=readiness_issues,
                draft_chars=count_delivery_chinese_content_chars(body),
                draft_machine_chars=count_delivery_chars(body),
                status=status,
            )
        )
    return records


def _scan_characters(root: Path) -> list[dict[str, str]]:
    char_dir = root / "characters"
    if not char_dir.exists():
        return []
    characters = []
    for path in sorted(char_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        characters.append(
            {
                "character_id": _scalar(text, "character_id") or path.stem,
                "name": _scalar(text, "name") or path.stem,
                "role": _scalar(text, "role"),
                "path": _rel_str(path, root),
            }
        )
    return characters


def _scan_foreshadowing(root: Path) -> list[dict[str, str]]:
    path = root / "plot" / "foreshadowing.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    clean_rows = []
    for row in rows:
        clean_rows.append({str(key or "").strip(): str(value or "").strip() for key, value in row.items()})
    return clean_rows


def _audit_issues(
    root: Path,
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
    chapter_files: list[Path],
    target_length: int,
    word_budget: dict[str, object],
) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    if not scenes:
        issues.append(
            LongformIssue(
                "high",
                "scene_inventory",
                "scenes/",
                "未发现任何场景文件，无法进行长篇连续性审计。",
                "先用场景模板建立至少一个 scenes/{scene_id}.yaml。",
            )
        )

    scene_ids = [scene.scene_id for scene in scenes]
    duplicates = sorted({scene_id for scene_id in scene_ids if scene_ids.count(scene_id) > 1})
    for scene_id in duplicates:
        issues.append(
            LongformIssue(
                "high",
                "scene_identity",
                scene_id,
                "发现重复 scene_id，后续草稿、审查和图谱节点会互相覆盖。",
                "为每个场景分配唯一 scene_id。",
            )
        )

    known_names = {item["character_id"] for item in characters} | {item["name"] for item in characters if item["name"]}
    for scene in scenes:
        if scene.chapter_id == "unassigned":
            issues.append(
                LongformIssue("medium", "chapter_structure", scene.scene_id, "场景缺少 chapter_id。", "补齐 chapter_id，避免章节装配时误分组。")
            )
        if not scene.location:
            issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 location。", "补齐地点以支持连续性和图谱审计。"))
        if not scene.participants:
            issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 participants。", "补齐参与人物以支持人物弧审计。"))
        if not scene.scene_goal:
            issues.append(LongformIssue("medium", "scene_schema", scene.scene_id, "场景缺少 scene_goal。", "补齐场景目标，避免章节节奏失焦。"))
        if scene.narrative_rhythm_status in {"", "defaulted", "incomplete"}:
            issues.append(
                LongformIssue(
                    "medium",
                    "narrative_rhythm",
                    scene.scene_id,
                    f"叙事节奏/场景桥接契约未显式通过：{scene.narrative_rhythm_status or 'missing'}。",
                    "补齐 scene_function、scene_turn、reader_effect、incoming_pressure 和 outgoing_hook，避免场景孤岛和平均速度叙事。",
                )
            )
        for participant in scene.participants:
            if known_names and participant not in known_names:
                issues.append(
                    LongformIssue(
                        "medium",
                        "character_inventory",
                        scene.scene_id,
                        f"参与者 `{participant}` 没有匹配的人物档案。",
                        "在 characters/ 中创建人物档案，或统一 participant 名称。",
                    )
                )
        if scene.status == "needs_draft":
            issues.append(LongformIssue("high", "draft_readiness", scene.scene_id, "场景缺少可审计正文草稿。", "运行 draft-scene 并补全正文草稿。"))
        elif scene.status == "needs_flow_gates":
            issues.append(
                LongformIssue(
                    "high",
                    "flow_readiness",
                    scene.scene_id,
                    "场景缺少正式场景链路门禁，不能进入章节或长篇 ready。",
                    "补齐 context、simulate-scene --agent、branch-simulate --agent、branch_selection.md 和 ready composition。",
                )
            )
        elif scene.status == "needs_review":
            issues.append(LongformIssue("high", "review_readiness", scene.scene_id, "场景有正文但缺少审查报告。", "运行 review-scene。"))
        elif scene.status == "needs_agent_review":
            issues.append(
                LongformIssue(
                    "high",
                    "review_readiness",
                    scene.scene_id,
                    "场景缺少平台 Agent 正式审查 JSON，不能进入 ready。",
                    "运行 agent-review-scene 生成任务，由平台 agent 填写 scene_review.v1 JSON 和 Markdown 报告。",
                )
            )
        elif scene.status == "needs_revision":
            issues.append(
                LongformIssue(
                    "high",
                    "review_readiness",
                    scene.scene_id,
                    "场景存在 pass_with_notes、warnings、revision_actions、style_notes 或未解决文风偏差。",
                    "运行 revise-scene 或记录正式 waiver 后重新进行静态/AgentReview。",
                )
            )
        elif scene.status == "blocked":
            issues.append(
                LongformIssue(
                    "high",
                    "review_readiness",
                    scene.scene_id,
                    f"场景审查未通过：{scene.review_conclusion or 'unknown'}。",
                    "根据审查报告修订后重新 review-scene。",
                )
            )

        context_path = root / "memory" / "context_packets" / f"{scene.scene_id}.md"
        if not context_path.exists():
            issues.append(LongformIssue("medium", "memory_context", scene.scene_id, "缺少场景上下文包。", "运行 context 或 draft-scene --rebuild-context。"))
        trace_status = context_trace_status(root, scene.scene_id, context_path=context_path)
        if not trace_status.passed:
            issues.append(
                LongformIssue(
                    "high",
                    "memory_context",
                    scene.scene_id,
                    f"场景上下文来源证明无效：{trace_status.message}",
                    "重跑 context 并检查 memory/context_packets/{scene_id}.trace.json。",
                )
            )

    chapter_ids = sorted({scene.chapter_id for scene in scenes if scene.chapter_id != "unassigned"})
    available_chapters = {path.stem for path in chapter_files}
    for chapter_id in chapter_ids:
        if chapter_id not in available_chapters:
            issues.append(
                LongformIssue(
                    "low",
                    "chapter_workspace",
                    chapter_id,
                    "缺少章节工作台 JSON。",
                    "运行 chapter-workspace 生成章节级状态对象。",
                )
            )

    draft_chars = sum(scene.draft_chars for scene in scenes)
    if target_length >= 100000 and not word_budget:
        issues.append(
            LongformIssue(
                "medium",
                "word_budget",
                "plot/word_budget/word_budget.json",
                "目标中文内容字符达到中长篇规模，但缺少长篇字数预算与剧情库存门禁。",
                "先运行 word-budget / longform-budget，并由平台 agent 根据任务侧车扩充预算化大纲候选。",
            )
        )
    if word_budget:
        totals = word_budget.get("totals", {})
        totals = totals if isinstance(totals, dict) else {}
        planned_scenes = _to_int(totals.get("scene_count"))
        budget_status = str(word_budget.get("status") or "")
        if budget_status == "needs_expansion":
            issues.append(
                LongformIssue(
                    "medium",
                    "word_budget",
                    "plot/word_budget/word_budget.json",
                    "预算报告显示现有大纲或场景库存不足，直接生成正文容易把长篇压缩成短篇摘要。",
                    "让平台 agent 处理 word_budget.agent_tasks.md，写出预算化大纲候选并通过 word-budget review。",
                )
            )
        if planned_scenes and scenes and len(scenes) < planned_scenes * 0.5:
            issues.append(
                LongformIssue(
                    "medium",
                    "scene_inventory",
                    "scenes/",
                    f"预算需要约 {planned_scenes} 个场景，目前仅登记 {len(scenes)} 个场景，剧情库存明显不足。",
                    "先扩充分卷、分章和场景列表，再进入批量正文生成。",
                )
            )
    if target_length > 0 and draft_chars < target_length * 0.2:
        issues.append(
            LongformIssue(
                "low",
                "scale_progress",
                "drafts",
                f"当前正文约 {draft_chars} 个中文内容字符，距离目标 {target_length} 个中文内容字符仍处于早期阶段。",
                "优先补齐场景草稿、章节工作台和连续性审查，再扩大生成规模。",
            )
        )

    for row in foreshadowing:
        status = _foreshadow_status(row)
        if status and status.lower() in RESOLVED_FORESHADOW_STATUSES:
            continue
        fid = row.get("foreshadow_id") or row.get("id") or "unknown"
        expected = row.get("expected_payoff") or row.get("expected_payoff_range") or ""
        actual = row.get("actual_payoff_scene") or row.get("payoff_scene") or ""
        if not expected and not actual:
            issues.append(
                LongformIssue(
                    "medium",
                    "foreshadowing_debt",
                    fid,
                    "伏笔缺少预期回收范围或实际回收场景。",
                    "补齐 expected_payoff_range 或 actual_payoff_scene，避免伏笔债务失控。",
                )
            )

    return issues


def _build_graph(
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
) -> dict:
    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(node_id: str, node_type: str, **attrs) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": node_type, **attrs})

    def add_edge(source: str, target: str, relation: str, **attrs) -> None:
        edges.append({"source": source, "target": target, "relation": relation, **attrs})

    character_lookup = {}
    for character in characters:
        cid = "character:" + (character["character_id"] or character["name"])
        add_node(cid, "character", name=character["name"], role=character["role"], path=character["path"])
        if character["character_id"]:
            character_lookup[character["character_id"]] = cid
        if character["name"]:
            character_lookup[character["name"]] = cid

    for scene in scenes:
        scene_node = "scene:" + scene.scene_id
        add_node(scene_node, "scene", chapter_id=scene.chapter_id, status=scene.status, path=scene.scene_path)
        if scene.location:
            location_node = "location:" + scene.location
            add_node(location_node, "location", name=scene.location)
            add_edge(scene_node, location_node, "located_at")
        for participant in scene.participants:
            character_node = character_lookup.get(participant, "character:" + participant)
            if participant not in character_lookup:
                add_node(character_node, "character_ref", name=participant)
            add_edge(character_node, scene_node, "appears_in")

    for prev, current in zip(scenes, scenes[1:]):
        add_edge("scene:" + prev.scene_id, "scene:" + current.scene_id, "next_scene")

    for row in foreshadowing:
        fid = row.get("foreshadow_id") or row.get("id") or ""
        if not fid:
            continue
        node = "foreshadow:" + fid
        add_node(node, "foreshadowing", status=_foreshadow_status(row), visibility=row.get("visibility", ""))
        setup = row.get("setup_scene") or ""
        payoff = row.get("actual_payoff_scene") or row.get("payoff_scene") or ""
        if setup:
            add_edge("scene:" + setup, node, "sets_up")
        if payoff:
            add_edge(node, "scene:" + payoff, "pays_off_at")

    return {
        "schema": "literary-engineering-workbench/longform-graph/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
    }


def _render_markdown(root: Path, payload: dict, graph_path: Path) -> str:
    summary = payload["summary"]
    issues = payload["issues"]
    scenes = payload["scenes"]
    foreshadowing = payload["foreshadowing"]
    lines = [
        "# 长篇项目审计报告",
        "",
        f"生成时间：{payload['generated_at']}",
        f"图谱文件：`{_rel_str(graph_path, root)}`",
        "",
        "## 总览",
        "",
        f"- 章节数：{summary['chapter_count']}",
        f"- 场景数：{summary['scene_count']}",
        f"- 人物档案数：{summary['character_count']}",
        f"- 地点数：{summary['location_count']}",
        f"- 正文中文内容字符：{summary['draft_chars']} / 目标 {summary['target_length']}",
        f"- 机器非空白字符诊断：{summary.get('draft_machine_chars', 0)}",
        f"- 字数预算状态：{summary.get('word_budget_status', 'missing')} / 预算场景 {summary.get('word_budget_scene_count', 0)}",
        f"- 可装配场景：{summary['ready_scene_count']}",
        f"- 阻塞场景：{summary['blocked_scene_count']}",
        f"- 节奏契约通过场景：{summary.get('rhythm_pass_count', 0)}",
        f"- 节奏契约缺口场景：{summary.get('rhythm_gap_count', 0)}",
        f"- 问题数：{summary['issue_count']}",
        "",
        "## 场景状态矩阵",
        "",
        "| 章节 | 场景 | 地点 | 参与者 | 正文中文内容字符 | 静态审查 | Agent审查 | 状态 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for scene in scenes:
        lines.append(
            "| {chapter} | {scene} | {location} | {participants} | {chars} | {review} | {agent_review} | {status} |".format(
                chapter=scene["chapter_id"],
                scene=scene["scene_id"],
                location=scene["location"] or "未填写",
                participants="、".join(scene["participants"]) or "未填写",
                chars=scene["draft_chars"],
                review=scene["review_conclusion"] or "missing",
                agent_review=f"{scene.get('agent_review_conclusion') or 'missing'}/{scene.get('agent_review_schema_status') or 'missing'}",
                status=scene["status"],
            )
        )

    lines.extend(["", "## 叙事节奏与场景桥接矩阵", ""])
    if scenes:
        lines.extend(["| 章节 | 场景 | 节奏契约 | 场景功能 | 本场转折 | 入场压力 | 出场钩子 |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for scene in scenes:
            lines.append(
                "| {chapter} | {scene} | {status} | {function} | {turn} | {incoming} | {outgoing} |".format(
                    chapter=scene["chapter_id"],
                    scene=scene["scene_id"],
                    status=scene.get("narrative_rhythm_status") or "missing",
                    function="、".join(scene.get("scene_function") or []) or "未填写",
                    turn=scene.get("scene_turn") or "未填写",
                    incoming=scene.get("incoming_pressure") or "未填写",
                    outgoing=scene.get("outgoing_hook") or "未填写",
                )
            )
    else:
        lines.append("- 未发现场景。")

    lines.extend(["", "## 风险清单", ""])
    if issues:
        lines.extend(["| 级别 | 类别 | 对象 | 问题 | 建议 |", "| --- | --- | --- | --- | --- |"])
        for issue in issues:
            lines.append(
                f"| {issue['severity']} | {issue['category']} | `{issue['subject']}` | {issue['message']} | {issue['recommendation']} |"
            )
    else:
        lines.append("- 未发现阻塞性风险。")

    lines.extend(["", "## 伏笔债务", ""])
    if foreshadowing:
        lines.extend(["| 伏笔 | 设置场景 | 预期回收 | 实际回收 | 状态 |", "| --- | --- | --- | --- | --- |"])
        for row in foreshadowing:
            lines.append(
                "| {fid} | {setup} | {expected} | {actual} | {status} |".format(
                    fid=row.get("foreshadow_id") or row.get("id") or "unknown",
                    setup=row.get("setup_scene") or "",
                    expected=row.get("expected_payoff") or row.get("expected_payoff_range") or "",
                    actual=row.get("actual_payoff_scene") or row.get("payoff_scene") or "",
                    status=_foreshadow_status(row) or "",
                )
            )
    else:
        lines.append("- 未登记伏笔。")

    lines.extend([
        "",
        "## 图谱导出",
        "",
        f"- 图谱 JSON：`{_rel_str(graph_path, root)}`",
        "- 当前是轻量 JSON 图谱，可后续导入 Neo4j 或由 LlamaIndex 图检索层消费。",
        "",
        "## 下一步",
        "",
        "- 先处理 `high` 风险，再扩大章节生成规模。",
        "- 每章运行 `chapter-workspace`，再运行本审计。",
        "- 对开放伏笔补齐预期回收范围。",
        "- 人物档案缺失时，先补人物 BDI，再继续正文扩写。",
    ])
    return "\n".join(lines) + "\n"


def _summary(
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, str]],
    foreshadowing: list[dict[str, str]],
    chapter_files: list[Path],
    issues: list[LongformIssue],
    target_length: int,
    word_budget: dict[str, object],
) -> dict[str, object]:
    chapter_ids = {scene.chapter_id for scene in scenes if scene.chapter_id != "unassigned"}
    locations = {scene.location for scene in scenes if scene.location}
    totals = word_budget.get("totals", {}) if word_budget else {}
    totals = totals if isinstance(totals, dict) else {}
    rhythm_curves = _rhythm_curves(scenes)
    return {
        "chapter_count": max(len(chapter_ids), len(chapter_files)),
        "scene_count": len(scenes),
        "character_count": len(characters),
        "location_count": len(locations),
        "foreshadowing_count": len(foreshadowing),
        "draft_chars": sum(scene.draft_chars for scene in scenes),
        "draft_chinese_chars": sum(scene.draft_chars for scene in scenes),
        "draft_machine_chars": sum(scene.draft_machine_chars for scene in scenes),
        "target_length": target_length,
        "ready_scene_count": sum(1 for scene in scenes if scene.status == "ready"),
        "blocked_scene_count": sum(1 for scene in scenes if scene.status != "ready"),
        "rhythm_pass_count": sum(1 for scene in scenes if scene.narrative_rhythm_status == "pass"),
        "rhythm_gap_count": sum(1 for scene in scenes if scene.narrative_rhythm_status in {"", "defaulted", "incomplete"}),
        "rhythm_curve_pass_count": sum(1 for curve in rhythm_curves.values() if curve.get("status") == "pass"),
        "rhythm_curve_attention_count": sum(1 for curve in rhythm_curves.values() if curve.get("status") != "pass"),
        "issue_count": len(issues),
        "word_budget_status": str(word_budget.get("status") or "missing") if word_budget else "missing",
        "word_budget_scene_count": _to_int(totals.get("scene_count")),
        "word_budget_chapter_count": _to_int(totals.get("chapter_count")),
    }


def _rhythm_curves(scenes: list[LongformSceneRecord]) -> dict[str, dict[str, object]]:
    chapters: dict[str, list[LongformSceneRecord]] = {}
    for scene in scenes:
        chapters.setdefault(scene.chapter_id, []).append(scene)
    return {
        chapter_id: analyze_narrative_rhythm_sequence([
            {
                "scene_id": scene.scene_id,
                "pace": scene.pace,
                "rhythm_role": scene.rhythm_role,
                "scene_function": list(scene.scene_function),
                "tension_curve": scene.tension_curve,
            }
            for scene in chapter_scenes
        ])
        for chapter_id, chapter_scenes in chapters.items()
    }


def _rhythm_curve_issues(curves: dict[str, dict[str, object]]) -> list[LongformIssue]:
    issues: list[LongformIssue] = []
    for chapter_id, curve in curves.items():
        for issue in curve.get("issues", []):
            if not isinstance(issue, dict):
                continue
            severity = "high" if issue.get("severity") == "blocking" else "medium"
            issues.append(LongformIssue(
                severity,
                "narrative_rhythm_curve",
                chapter_id,
                str(issue.get("message") or "章节叙事节奏曲线需要复核。"),
                "回到场景编排，调整场景功能、推进速度或 entry/peak/exit 张力交接；不要只靠正文修辞制造假高潮。",
            ))
    return issues


def _review_conclusion(text: str) -> str:
    match = re.search(r"(?m)^-\s*结论：\s*(\S+)\s*$", text)
    return match.group(1).strip() if match else ""


def _foreshadow_status(row: dict[str, str]) -> str:
    return row.get("status") or row.get("状态") or ""


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def _list_after(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return []
    inline = match.group(1).strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [item.strip().strip("\"'") for item in inline.strip("[]").split(",") if item.strip()]
    lines = text[match.end() :].splitlines()
    values = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            values.append(stripped.strip("- ").strip("\"'"))
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
            break
    return values


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _outgoing_hook_text(bridge: dict[str, object]) -> str:
    direct = str(bridge.get("outgoing_hook") or "").strip()
    if direct:
        return direct
    hooks = bridge.get("outgoing_hooks")
    if not isinstance(hooks, list):
        return ""
    parts: list[str] = []
    for item in hooks:
        if isinstance(item, dict):
            content = str(item.get("content") or item.get("summary") or "").strip()
            if content:
                parts.append(content)
        else:
            text = str(item).strip()
            if text:
                parts.append(text)
    return "；".join(parts)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _existing_rel(path: Path, root: Path) -> str:
    return _rel_str(path, root) if path.exists() else ""
