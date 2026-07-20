"""Chapter-level workspace assembly."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .context_broker import default_context_trace_path
from .draft_text import count_delivery_chars, count_delivery_chinese_content_chars, final_body_from_draft_text
from .platform_agent_tasks import write_platform_scene_review_task
from .review_ci import review_scene_draft
from .narrative_rhythm import narrative_rhythm_contract
from .scene_draft import build_scene_draft
from .scene_readiness import agent_review_gate_state, scene_flow_gate_issues, scene_readiness_status


@dataclass(frozen=True)
class SceneChapterRecord:
    scene_id: str
    scene_path: str
    chapter_id: str
    location: str
    participants: tuple[str, ...]
    scene_goal: str
    context_path: str
    context_trace_path: str
    simulation_path: str
    draft_path: str
    review_path: str
    review_conclusion: str
    agent_review_path: str
    agent_review_json: str
    agent_review_validation: str
    agent_review_conclusion: str
    agent_review_schema_status: str
    agent_review_source_match: bool
    agent_review_unresolved_notes: tuple[str, ...]
    style_adherence_status: str
    word_budget_adherence_status: str
    reader_experience_adherence_status: str
    reader_promise_satisfied: bool
    narrative_rhythm_status: str
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
    writeback_candidates: tuple[str, ...]


@dataclass(frozen=True)
class ChapterWorkspaceResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    chapter_id: str
    scene_count: int
    ready_count: int
    blocked_count: int


def build_chapter_workspace(
    project_root: Path,
    chapter_id: str = "chapter_0001",
    scenes: Iterable[Path] | None = None,
    build_missing: bool = False,
    review_drafts: bool = False,
    agent_review: bool = False,
    output: Path | None = None,
    json_output: Path | None = None,
) -> ChapterWorkspaceResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    selected_scenes = _select_scene_paths(root, chapter_id, scenes)
    if not selected_scenes:
        raise FileNotFoundError(f"no scene files found for chapter: {chapter_id}")

    records = []
    for scene_path in selected_scenes:
        records.append(
            _build_scene_record(
                root,
                scene_path,
                requested_chapter_id=chapter_id,
                build_missing=build_missing,
                review_drafts=review_drafts,
                agent_review=agent_review,
            )
        )

    markdown_path = _resolve_output(root, output, "drafts", "chapters", f"{chapter_id}.md")
    json_path = _resolve_output(root, json_output, "plot", "chapters", f"{chapter_id}.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "literary-engineering-workbench/chapter-workspace/v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chapter_id": chapter_id,
        "project_root": str(root),
        "scenes": [asdict(record) for record in records],
        "summary": _chapter_summary(records),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_chapter_markdown(root, chapter_id, records, json_path), encoding="utf-8")

    blocked = [record for record in records if record.status != "ready"]
    ready = [record for record in records if record.status == "ready"]
    return ChapterWorkspaceResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        chapter_id=chapter_id,
        scene_count=len(records),
        ready_count=len(ready),
        blocked_count=len(blocked),
    )


def _select_scene_paths(root: Path, chapter_id: str, scenes: Iterable[Path] | None) -> list[Path]:
    if scenes:
        selected = []
        for item in scenes:
            path = item if item.is_absolute() else root / item
            if not path.exists():
                raise FileNotFoundError(f"scene file not found: {path}")
            selected.append(path.resolve())
        return selected

    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []

    candidates = sorted(path.resolve() for path in scene_dir.glob("*.yaml") if not path.name.startswith("_"))
    matching = [path for path in candidates if _scene_chapter_id(_read(path)) == chapter_id]
    return matching or candidates


def _build_scene_record(
    root: Path,
    scene_path: Path,
    requested_chapter_id: str,
    build_missing: bool,
    review_drafts: bool,
    agent_review: bool,
) -> SceneChapterRecord:
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_id = _scene_chapter_id(scene_text) or requested_chapter_id

    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    context_trace_path = default_context_trace_path(context_path)
    draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"
    review_path = root / "reviews" / f"{scene_id}-review.md"
    agent_review_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.md"
    agent_review_json_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    simulation_path = root / "branches" / scene_id / "roleplay_simulation.md"
    composition_json_path = root / "drafts" / "compositions" / f"{scene_id}_composition.json"

    if build_missing and not draft_path.exists():
        build_scene_draft(root, scene=_relative(scene_path, root), rebuild_context=not context_path.exists())

    if review_drafts and draft_path.exists():
        review_scene_draft(root, draft_path, output=review_path)

    if agent_review and draft_path.exists():
        write_platform_scene_review_task(
            root,
            scene_path=scene_path,
            draft_path=draft_path,
            report_path=agent_review_path,
            json_path=agent_review_json_path,
        )

    draft_text = _read(draft_path)
    review_text = _read(review_path)
    body = final_body_from_draft_text(draft_text) if draft_text else ""
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

    return SceneChapterRecord(
        scene_id=scene_id,
        scene_path=_rel_str(scene_path, root),
        chapter_id=chapter_id,
        location=_scalar(scene_text, "location"),
        participants=tuple(_list_after(scene_text, "participants")),
        scene_goal=_scalar(scene_text, "scene_goal"),
        context_path=_existing_rel(context_path, root),
        context_trace_path=_existing_rel(context_trace_path, root),
        simulation_path=_existing_rel(simulation_path, root),
        draft_path=_existing_rel(draft_path, root),
        review_path=_existing_rel(review_path, root),
        review_conclusion=conclusion,
        agent_review_path=_existing_rel(agent_review_path, root),
        agent_review_json=_existing_rel(agent_review_json_path, root),
        agent_review_validation=str(agent_state.get("validation_path") or ""),
        agent_review_conclusion=str(agent_state.get("conclusion") or ""),
        agent_review_schema_status=str(agent_state.get("schema_status") or ""),
        agent_review_source_match=bool(agent_state.get("source_match")),
        agent_review_unresolved_notes=tuple(str(item) for item in agent_state.get("unresolved_notes", [])),
        style_adherence_status=str(agent_state.get("style_adherence_status") or ""),
        word_budget_adherence_status=str(agent_state.get("word_budget_adherence_status") or ""),
        reader_experience_adherence_status=str(agent_state.get("reader_experience_adherence_status") or ""),
        reader_promise_satisfied=bool(agent_state.get("reader_promise_satisfied")),
        narrative_rhythm_status=str(rhythm_contract.get("status") or ""),
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
        writeback_candidates=tuple(_writeback_candidates(draft_text)),
    )


def _render_chapter_markdown(root: Path, chapter_id: str, records: list[SceneChapterRecord], json_path: Path) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = _chapter_summary(records)
    lines = [
        f"# 章节工作台：{chapter_id}",
        "",
        f"生成时间：{generated_at}",
        f"状态文件：`{_rel_str(json_path, root)}`",
        "",
        "## 使用规则",
        "",
        "- 本文件是章节级工程工作台，不是最终正稿。",
        "- 只有 flow gates、静态场景审查和 Agent 场景审查都干净通过后，场景正文才可进入章节装配区。",
        "- `pass_with_notes`、warnings、revision_actions、style_notes 或未解决的文风偏差必须先进入 `revise-scene` 或记录正式 waiver。",
        "- 跨场景新增事实、人物变化和伏笔变化必须进入写回候选，等待人工确认。",
        "- Dify 或其他前台工具可以展示本文件，但不得绕过后端直接写回 canon。",
        "",
        "## 章节状态",
        "",
        f"- 场景数：{summary['scene_count']}",
        f"- 可装配：{summary['ready_count']}",
        f"- 阻塞/待处理：{summary['blocked_count']}",
        f"- 总正文中文内容字符：{summary['draft_chars']}",
        f"- 机器非空白字符诊断：{summary.get('draft_machine_chars', 0)}",
        "",
        "## 场景清单",
        "",
        "| 场景 | 地点 | 参与者 | 目标 | 正文中文内容字符 | 静态审查 | Agent审查 | 状态 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| {scene_id} | {location} | {participants} | {scene_goal} | {draft_chars} | {review} | {agent_review} | {status} |".format(
                scene_id=record.scene_id,
                location=record.location or "未填写",
                participants="、".join(record.participants) or "未填写",
                scene_goal=record.scene_goal or "未填写",
                draft_chars=record.draft_chars,
                review=record.review_conclusion or "missing",
                agent_review=_agent_review_label(record),
                status=record.status,
            )
        )

    lines.extend([
        "",
        "## 叙事节奏与场景桥接",
        "",
        "| 场景 | 节奏契约 | 场景功能 | 本场转折 | 入场压力 | 出场钩子 |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for record in records:
        lines.append(
            "| {scene} | {status} | {function} | {turn} | {incoming} | {outgoing} |".format(
                scene=record.scene_id,
                status=record.narrative_rhythm_status or "missing",
                function="、".join(record.scene_function) or "未填写",
                turn=record.scene_turn or "未填写",
                incoming=record.incoming_pressure or "未填写",
                outgoing=record.outgoing_hook or "未填写",
            )
        )

    lines.extend([
        "",
        "## 门禁问题汇总",
        "",
    ])
    issue_found = False
    for record in records:
        if not record.readiness_issues:
            continue
        issue_found = True
        lines.append(f"### {record.scene_id}")
        lines.append("")
        for issue in record.readiness_issues:
            lines.append(f"- {issue}")
        lines.append("")
    if not issue_found:
        lines.append("- 所有场景通过章节装配门禁。")

    lines.extend([
        "",
        "## 产物矩阵",
        "",
        "| 场景 | Context | Simulation | Draft | Review | Agent Review |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for record in records:
        lines.append(
            f"| {record.scene_id} | `{record.context_path or 'missing'}` | `{record.simulation_path or 'missing'}` | `{record.draft_path or 'missing'}` | `{record.review_path or 'missing'}` | `{record.agent_review_json or 'missing'}` |"
        )

    lines.extend([
        "",
        "## 连续性检查",
        "",
    ])
    lines.extend(_continuity_lines(records))

    lines.extend([
        "",
        "## 章节正文装配区",
        "",
    ])
    for record in records:
        lines.extend(_draft_excerpt_lines(root, record))

    lines.extend([
        "",
        "## 写回候选汇总",
        "",
    ])
    has_candidates = False
    for record in records:
        if not record.writeback_candidates:
            continue
        has_candidates = True
        lines.append(f"### {record.scene_id}")
        lines.append("")
        for item in record.writeback_candidates:
            lines.append(f"- {item}")
        lines.append("")
    if not has_candidates:
        lines.append("- 暂无可汇总写回候选。")

    lines.extend([
        "",
        "## 人工确认",
        "",
        "- [ ] 本章所有 `blocked` 场景已修订。",
        "- [ ] 本章所有 `needs_agent_review` 场景已完成 Agent 场景审查。",
        "- [ ] 所有新 canon 候选已进入候选区，而非直接确认为事实。",
        "- [ ] 人物状态变化在相邻场景之间连续。",
        "- [ ] 伏笔设置和回收没有互相冲突。",
        "- [ ] 章节导出前已完成最终审查。",
    ])

    return "\n".join(lines) + "\n"


def _draft_excerpt_lines(root: Path, record: SceneChapterRecord) -> list[str]:
    lines = [f"### {record.scene_id}", ""]
    if record.status != "ready":
        lines.append(f"- 当前状态：{record.status}，暂不装配正文。")
        if record.readiness_issues:
            lines.append("- 阻塞原因：" + "；".join(record.readiness_issues[:4]))
        lines.append("")
        return lines
    draft_path = root / record.draft_path if record.draft_path else Path()
    body = final_body_from_draft_text(_read(draft_path)) if draft_path.exists() else ""
    if not body:
        lines.append("- 审查通过记录存在，但未读取到正文。")
    else:
        lines.append(body)
    lines.append("")
    return lines


def _continuity_lines(records: list[SceneChapterRecord]) -> list[str]:
    lines = []
    if not records:
        return ["- 未发现章节场景。"]
    for prev, current in zip(records, records[1:]):
        lines.append(f"- `{prev.scene_id}` -> `{current.scene_id}`：检查人物状态、地点移动、时间推进和伏笔承接。")
    if len(records) == 1:
        lines.append("- 本章当前只有一个场景，连续性检查需要在新增场景后执行。")
    blocked = [record.scene_id for record in records if record.status != "ready"]
    if blocked:
        lines.append("- 阻塞场景：" + "、".join(blocked))
    else:
        lines.append("- 所有场景均可进入章节装配。")
    return lines


def _chapter_summary(records: list[SceneChapterRecord]) -> dict[str, int]:
    return {
        "scene_count": len(records),
        "ready_count": sum(1 for record in records if record.status == "ready"),
        "blocked_count": sum(1 for record in records if record.status != "ready"),
        "draft_chars": sum(record.draft_chars for record in records),
        "draft_chinese_chars": sum(record.draft_chars for record in records),
        "draft_machine_chars": sum(record.draft_machine_chars for record in records),
        "rhythm_pass_count": sum(1 for record in records if record.narrative_rhythm_status == "pass"),
        "rhythm_incomplete_count": sum(1 for record in records if record.narrative_rhythm_status == "incomplete"),
    }


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


def _review_conclusion(text: str) -> str:
    match = re.search(r"(?m)^-\s*结论：\s*(\S+)\s*$", text)
    return match.group(1).strip() if match else ""


def _agent_review_label(record: SceneChapterRecord) -> str:
    conclusion = record.agent_review_conclusion or "missing"
    schema = record.agent_review_schema_status or "missing"
    return f"{conclusion}/{schema}"


def _writeback_candidates(draft_text: str) -> list[str]:
    candidates = []
    for heading in ["### 新增事实候选", "### 人物状态变化", "### 关系变化", "### 伏笔变化", "### 需要人工确认"]:
        section = _section_after_heading(draft_text, heading)
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") and stripped.strip("- ").strip():
                candidates.append(f"{heading.replace('### ', '')}：{stripped.strip('- ').strip()}")
    return candidates


def _section_after_heading(text: str, heading: str) -> str:
    idx = text.find(heading)
    if idx < 0:
        return ""
    next_idx = text.find("\n### ", idx + 1)
    if next_idx < 0:
        next_idx = text.find("\n## ", idx + 1)
    return text[idx: next_idx if next_idx >= 0 else len(text)]


def _scene_chapter_id(scene_text: str) -> str:
    return _scalar(scene_text, "chapter_id")


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    return value.strip("\"'")


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


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _existing_rel(path: Path, root: Path) -> str:
    return _rel_str(path, root) if path.exists() else ""
