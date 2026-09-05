"""Route-neutral helpers for the persistent workflow-state ledger.

This module intentionally contains no literary route decisions.  Route state
calculators consume these small file, sidecar, and rendering primitives while
the facade in :mod:`workflow_state` owns payload assembly and persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ..agent_tasks import agent_task_completion_status
from ..tasking.semantic_contracts import semantic_artifact_errors, semantic_artifact_relative_path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _slug_profile_id(value: str) -> str:
    text = value.strip().lower().replace("\\", "/").replace("/", "-").replace("_", "-")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "style-profile"


def _file_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    return {
        "key": key,
        "status": "pass" if path.exists() else "missing",
        "path": str(path),
        "message": "exists" if path.exists() else "missing",
        "next_action": "" if path.exists() else next_action,
    }


def _task_step(key: str, root: Path, path: Path, next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(path, root=root)
    complete = state.get("complete") is True
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "message": state.get("message", ""),
        "next_action": "" if complete else next_action,
    }


def _semantic_task_step(key: str, root: Path, scene_id: str, path: Path, next_action: str) -> dict[str, object]:
    """A sidecar is complete only with its typed semantic artifact."""

    state = agent_task_completion_status(path, root=root)
    errors = semantic_artifact_errors(root, key, scene_id)
    complete = state.get("complete") is True and not errors
    semantic_path = semantic_artifact_relative_path(key, scene_id)
    message = str(state.get("message") or "")
    if errors:
        message = (message + "; " if message else "") + "; ".join(errors[:3])
    return {
        "key": key,
        "status": "pass" if complete else ("semantic_incomplete" if state.get("complete") is True else str(state.get("status") or "pending")),
        "path": _rel(path, root),
        "completion": state.get("completion", ""),
        "semantic_artifact": semantic_path,
        "message": message,
        "next_action": "" if complete else next_action,
    }


def _static_review_conclusion(path: Path) -> str:
    text = _read(path)
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _longform_review_step(key: str, path: Path, next_action: str) -> dict[str, object]:
    conclusion = _static_review_conclusion(path)
    return {
        "key": key,
        "status": "pass" if conclusion == "pass" else conclusion or "missing",
        "path": str(path),
        "message": f"conclusion={conclusion or 'missing'}",
        "next_action": "" if conclusion == "pass" else next_action,
    }


def _approval_record(root: Path, candidate_id: str) -> dict[str, object]:
    """Return the latest durable approval record for a run id."""

    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == candidate_id:
            latest = payload
    return latest


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Formal Route State：{payload['route']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 场景数：{summary['scene_count']}",
        f"- Ready：{summary['ready_count']}",
        f"- Blocked：{summary['blocked_count']}",
        f"- Next actions：{summary['next_action_count']}",
        "",
        "## Scene State",
        "",
        "| 场景 | 状态 | 当前步骤 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.append(
            f"| {scene.get('scene_id', '')} | {scene.get('status', '')} | {scene.get('current_step', '')} | {scene.get('next_action', '')} |"
        )
    longform = payload.get("longform") if isinstance(payload.get("longform"), dict) else {}
    if longform:
        lines.extend(["", "## Longform State", ""])
        lines.append(
            f"- 状态：`{longform.get('status', '')}`；当前步骤：`{longform.get('current_step', '')}`；下一步：{longform.get('next_action', '') or 'n/a'}"
        )
        lines.extend(["", "| 步骤 | 状态 | 信息 |", "| --- | --- | --- |"])
        for step in longform.get("steps", []):
            if not isinstance(step, dict):
                continue
            lines.append(f"| {step.get('key', '')} | {step.get('status', '')} | {step.get('message', '')} |")
    source_ingests = payload.get("source_ingests") if isinstance(payload.get("source_ingests"), list) else []
    if source_ingests:
        lines.extend(["", "## Source Ingest State", "", "| work_id | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in source_ingests:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('work_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    styles = payload.get("styles") if isinstance(payload.get("styles"), list) else []
    if styles:
        lines.extend(["", "## Style Engineering State", "", "| profile | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in styles:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('profile_dir', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    if assets:
        lines.extend(["", "## Asset State", "", "| candidate | 类型 | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- | --- |"])
        for item in assets:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('candidate_id', '')} | {item.get('asset_type', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    audits = payload.get("audits") if isinstance(payload.get("audits"), list) else []
    if audits:
        lines.extend(["", "## Review And Audit State", "", "| target | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in audits:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('target_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    exports = payload.get("exports") if isinstance(payload.get("exports"), list) else []
    if exports:
        lines.extend(["", "## Export And Release State", "", "| chapter | 状态 | 当前步骤 | 下一步 |", "| --- | --- | --- | --- |"])
        for item in exports:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| {item.get('chapter_id', '')} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('next_action', '')} |"
            )
    lines.extend(["", "## Details", ""])
    for scene in payload.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        lines.extend([f"### {scene.get('scene_id', '')}", ""])
        for step in scene.get("steps", []):
            if isinstance(step, dict):
                lines.append(f"- `{step.get('key', '')}`：{step.get('status', '')}。{step.get('message', '')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
