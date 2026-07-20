"""Tool-layer agent task sidecar helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .punctuation_standard import PUNCTUATION_STANDARD_SHORT_RULE
from .resources import engine_path


AGENT_TASK_MARKER = "[AGENT_TASK:"
COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
COMPLETE_STATUSES = {"complete", "completed", "done", "handled", "pass"}


def default_agent_tasks_path(artifact_path: Path) -> Path:
    """Return the sidecar path for platform-agent task instructions."""

    return artifact_path.with_suffix(".agent_tasks.md")


def default_agent_completion_path(task_path: Path) -> Path:
    """Return the completion-marker path for a platform-agent task sidecar."""

    name = task_path.name
    suffix = ".agent_tasks.md"
    if name.endswith(suffix):
        return task_path.with_name(name[: -len(suffix)] + ".agent_completion.json")
    return task_path.with_suffix(".agent_completion.json")


def agent_task_completion_status(task_path: Path, *, root: Path | None = None) -> dict[str, object]:
    """Inspect whether a platform-agent sidecar has been explicitly handled."""

    completion_path = default_agent_completion_path(task_path)
    rel_task = _rel(task_path, root or task_path.parent)
    rel_completion = _rel(completion_path, root or completion_path.parent)
    state: dict[str, object] = {
        "status": "missing_task" if not task_path.exists() else "pending",
        "complete": False,
        "task": rel_task,
        "completion": rel_completion,
        "message": "",
    }
    if not task_path.exists():
        state["message"] = f"task sidecar missing: {rel_task}"
        return state
    if not completion_path.exists():
        state["message"] = f"missing explicit platform-agent completion marker: {rel_completion}"
        return state
    try:
        payload = json.loads(completion_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state["status"] = "invalid_completion"
        state["message"] = f"completion marker is not valid JSON: {rel_completion}"
        return state
    if not isinstance(payload, dict):
        state["status"] = "invalid_completion"
        state["message"] = f"completion marker root is not an object: {rel_completion}"
        return state
    marker_status = str(payload.get("status") or "").strip().lower()
    completed = payload.get("completed") is True or marker_status in COMPLETE_STATUSES
    if not completed:
        state["status"] = marker_status or "pending"
        state["message"] = f"completion marker is not complete: {rel_completion}"
        return state
    if payload.get("expected_artifacts_checked") is False:
        state["status"] = "unchecked"
        state["message"] = f"completion marker did not check expected artifacts: {rel_completion}"
        return state
    state.update(
        {
            "status": "complete",
            "complete": True,
            "message": f"platform-agent task completed: {rel_completion}",
            "handled_by": str(payload.get("handled_by") or ""),
            "completed_at": str(payload.get("completed_at") or ""),
        }
    )
    return state


def write_agent_completion_marker(
    task_path: Path,
    *,
    root: Path | None = None,
    handled_by: str = "platform-agent",
    notes: list[str] | None = None,
) -> Path:
    """Write an explicit completion marker for tests or platform-agent handoff scripts."""

    completion = default_agent_completion_path(task_path)
    completion.parent.mkdir(parents=True, exist_ok=True)
    base = root or task_path.parent
    payload = {
        "schema": COMPLETION_SCHEMA,
        "source_task": _rel(task_path, base),
        "status": "complete",
        "handled_by": handled_by,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "expected_artifacts_checked": True,
        "notes": notes or [],
    }
    completion.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return completion


def render_agent_task_block(instruction: str) -> str:
    text = instruction.strip()
    return f"{AGENT_TASK_MARKER} {text}\n]"


def write_agent_tasks(
    output_path: Path,
    *,
    title: str,
    root: Path,
    source_paths: list[Path],
    tasks: list[tuple[str, str]],
    notes: list[str] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expanded_sources = list(source_paths)
    punctuation_ref = _punctuation_reference()
    if punctuation_ref and punctuation_ref not in expanded_sources:
        expanded_sources.append(punctuation_ref)
    output_path.write_text(
        render_agent_tasks_document(
            title=title,
            root=root,
            source_paths=expanded_sources,
            tasks=tasks,
            notes=notes or [],
            task_path=output_path,
        ),
        encoding="utf-8",
    )
    return output_path


def render_agent_tasks_document(
    *,
    title: str,
    root: Path,
    source_paths: list[Path],
    tasks: list[tuple[str, str]],
    notes: list[str],
    task_path: Path | None = None,
) -> str:
    completion_path = default_agent_completion_path(task_path) if task_path else None
    completion_rel = _rel(completion_path, root) if completion_path else "同名 `.agent_completion.json`"
    task_rel = _rel(task_path, root) if task_path else "当前 .agent_tasks.md"
    lines = [
        f"# 平台 Agent 任务说明：{title}",
        "",
        "本文件给装载本 Skill 的 Codex / Claude / 工具层平台 agent 执行。",
        "它不是外部 LLM prompt，不是 canon，不是正式剧情内容；命令写出本文件只表示“任务已准备好”，不表示任务完成。",
        "当前平台 agent 应读取本文件、执行判断或创作、写入下方要求的目标产物，并创建完成标记后，才能继续晋升、导出或回复用户。",
        f"完成标记：`{completion_rel}`。缺少该文件时，本 sidecar 视为未处理。",
        "",
        "## Source Artifacts",
        "",
    ]
    if source_paths:
        for path in source_paths:
            lines.append(f"- `{_rel(path, root)}`")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## Execution Rules",
            "",
            "- 先确认本任务所属 route，并读取 `SKILL.md`、`AGENTS.md`、`agentread.yaml`、`references/agent-run-protocol.md` 以及该 route 在 `agentread.yaml` 中列出的文档。",
            "- 在最终报告或目标 Markdown 中写明 reading receipt：route、已读文档、已检查项目状态、仍缺失的上下文。",
            "- 先读取 Source Artifacts，再执行下列任务。",
            "- 不要因为任务名称包含 agent / review / style / JSON 就判断自己不能做；如需 CLI 辅助，先运行 `--help` 或 `protocol <route>`，失败后记录真实错误。",
            "- 若本任务要求写 review JSON、候选正文、修订报告、分支选择或状态补丁，当前平台 agent 应直接完成这些产物；不要等待“外部 agent”。",
            "- 若本任务要求写候选正文、修订正文、正文草稿或可交付正文，必须由当前主平台 agent 亲自完成；subagent 只能做资料整理、上下文摘录、schema/格式检查、连续性清单、风险标注等相对机械工作，不得代写正文。",
            "- 正式 Skill 宿主不得使用 `--allow-unreviewed`、`--allow-review-notes`、`--include-blocked`、`--allow-unapproved` 等调试/跳审参数绕过 review；遇到阻塞门禁时补齐 review、revision、approval 或 route-audit。",
            "- 任何新增事实、人物状态变化、分支选择和发布判断都保持候选状态。",
            "- 不要把本文件中的任务标记写入 JSON、prompt manifest、正稿、canon 或发布包。",
            f"- 未创建 `{completion_rel}` 前，不得把本任务称为完成；后续正式命令会检查该完成标记。",
            "- 如发现任务与 canon、角色事实、文风挂载或用户约束冲突，先记录冲突并请求确认。",
            f"- {PUNCTUATION_STANDARD_SHORT_RULE}",
        ]
    )
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(["", "## Tasks", ""])
    for index, (heading, body) in enumerate(tasks, start=1):
        lines.extend(
            [
                f"### {index}. {heading}",
                "",
                render_agent_task_block(body),
                "",
            ]
        )
    lines.extend(
        [
            f"### {len(tasks) + 1}. 写入任务完成标记",
            "",
            render_agent_task_block(
                f"""完成以上目标产物并亲自检查后，创建或覆盖 `{completion_rel}`，内容必须是 JSON：
{{
  "schema": "{COMPLETION_SCHEMA}",
  "source_task": "{task_rel}",
  "status": "complete",
  "handled_by": "platform-agent",
  "completed_at": "ISO-8601 时间",
  "expected_artifacts_checked": true,
  "notes": []
}}
不得在未读取 Source Artifacts、未完成目标产物或未检查产物前写入该完成标记。"""
            ),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _punctuation_reference() -> Path | None:
    path = engine_path("references", "punctuation-standard.md")
    return path if path.exists() else None
