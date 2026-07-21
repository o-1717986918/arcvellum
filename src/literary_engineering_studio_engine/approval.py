"""Workflow approval records and follow-up task generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


APPROVAL_DECISIONS = {"approve", "revise", "reject", "defer"}


@dataclass(frozen=True)
class ApprovalResult:
    approval_path: Path
    index_path: Path
    task_path: Path | None
    decision: str


@dataclass(frozen=True)
class ApprovalSummaryResult:
    output_path: Path
    record_count: int
    task_count: int


def record_workflow_approval(
    project_root: Path,
    run_id: str,
    decision: str,
    actor: str = "human",
    notes: str = "",
    subject_sha256: str = "",
) -> ApprovalResult:
    root = project_root.resolve()
    safe_run_id = _validate_run_id(run_id)
    decision = decision.strip()
    if decision not in APPROVAL_DECISIONS:
        raise ValueError("decision must be one of: approve, revise, reject, defer")

    approvals_dir = root / "workflow" / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    approval_path = approvals_dir / f"{safe_run_id}.jsonl"
    index_path = approvals_dir / "index.jsonl"
    recorded_at = _now()
    task_path = _write_followup_task(root, safe_run_id, decision, actor, notes, recorded_at)
    record = {
        "schema": "literary-engineering-workbench/workflow-approval/v0.2",
        "run_id": safe_run_id,
        "decision": decision,
        "actor": actor,
        "notes": notes,
        "recorded_at": recorded_at,
        "task_path": _rel_str(task_path, root) if task_path else "",
        "subject_sha256": subject_sha256.strip().lower(),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with approval_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return ApprovalResult(approval_path=approval_path, index_path=index_path, task_path=task_path, decision=decision)


def build_approval_summary(project_root: Path, run_id: str = "", output: Path | None = None) -> ApprovalSummaryResult:
    root = project_root.resolve()
    records = _load_approval_index(root)
    if run_id:
        safe_run_id = _validate_run_id(run_id)
        records = [record for record in records if record.get("run_id") == safe_run_id]
    output_path = output or root / "workflow" / "approvals" / "approval_summary.md"
    output_path = output_path if output_path.is_absolute() else root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = _render_summary(records, root, run_id=run_id)
    output_path.write_text(text, encoding="utf-8")
    task_count = sum(1 for record in records if record.get("task_path"))
    return ApprovalSummaryResult(output_path=output_path, record_count=len(records), task_count=task_count)


def _load_approval_index(root: Path) -> list[dict[str, object]]:
    index_path = root / "workflow" / "approvals" / "index.jsonl"
    if not index_path.exists():
        return []
    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _write_followup_task(root: Path, run_id: str, decision: str, actor: str, notes: str, recorded_at: str) -> Path | None:
    if decision in {"approve", "defer"}:
        return None
    tasks_dir = root / "workflow" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    stamp = recorded_at.replace(":", "").replace("+", "Z").replace(".", "-")
    task_path = tasks_dir / f"{run_id}-{decision}-{stamp}.md"
    log_path = root / "workflow" / "runs" / run_id / "workflow_log.md"
    state_path = root / "workflow" / "runs" / run_id / "workflow_state.json"
    lines = [
        f"# Workflow Follow-up Task：{run_id}",
        "",
        f"- 决策：`{decision}`",
        f"- 记录人：{actor or 'human'}",
        f"- 记录时间：{recorded_at}",
        f"- 状态文件：`{_rel_str(state_path, root)}`",
        f"- 日志文件：`{_rel_str(log_path, root)}`",
        "",
        "## 审批意见",
        "",
        notes or "- 未填写。",
        "",
        "## 处理要求",
        "",
        "- 读取 workflow state 和 workflow log，定位 blocked、failed 或被人工指出的问题。",
        "- 修改草稿、场景、人物或上下文候选时，不得直接写 canon。",
        "- 完成后重新运行相关 workflow，并在新的 run 中通过 `--resume-run-id` 关联本次 run。",
    ]
    if decision == "reject":
        lines.append("- reject 表示当前产物不得进入发布候选，必须重新生成或重构方案。")
    else:
        lines.append("- revise 表示允许保留可用部分，但必须完成修订后再审。")
    task_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return task_path


def _render_summary(records: list[dict[str, object]], root: Path, run_id: str = "") -> str:
    title = f"# Approval Summary：{run_id}" if run_id else "# Approval Summary"
    lines = [title, "", f"- 项目：`{root}`", f"- 记录数：{len(records)}", ""]
    if not records:
        lines.append("- 暂无审批记录。")
        return "\n".join(lines) + "\n"
    lines.extend(["| Run | Decision | Actor | Task | Recorded At |", "| --- | --- | --- | --- | --- |"])
    for record in records:
        task = record.get("task_path") or ""
        lines.append(
            "| `{run}` | {decision} | {actor} | {task} | {time} |".format(
                run=record.get("run_id", ""),
                decision=record.get("decision", ""),
                actor=record.get("actor", ""),
                task=f"`{task}`" if task else "",
                time=record.get("recorded_at", ""),
            )
        )
    lines.extend(["", "## Notes", ""])
    note_count = 0
    for record in records:
        notes = str(record.get("notes") or "").strip()
        if notes:
            note_count += 1
            lines.append(f"- `{record.get('run_id', '')}`：{notes}")
    if note_count == 0:
        lines.append("- 无。")
    return "\n".join(lines) + "\n"


def _validate_run_id(value: str) -> str:
    run_id = value.strip()
    if not run_id:
        raise ValueError("run_id must not be empty")
    if len(run_id) > 128 or ".." in run_id or any(char in run_id for char in "/\\"):
        raise ValueError("run_id must be a single safe filename segment")
    if any(ord(char) < 32 for char in run_id):
        raise ValueError("run_id may not contain control characters")
    return run_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
