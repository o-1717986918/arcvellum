"""Read-only evidence helpers for export and release Gates."""

from __future__ import annotations

import json
from pathlib import Path
import re

from ...task_paths import relative_path as _rel


DELIVERY_TRACE_PATTERNS = {
    "scene-id": r"\bscene_\d{4}\b",
    "agent-task": r"\[AGENT_TASK:",
    "canon-note-heading": r"(?m)^#{1,4}\s*(新增事实候选|人物状态变化|关系变化|伏笔变化|需要人工确认|世界状态变化|状态变化候选)\s*$",
    "review-heading": r"(?m)^#{1,4}\s*(审查|AgentReview|Route Audit|平台 Agent 任务|门禁问题汇总)\b",
    "workflow-path": r"\b(workflow/tasks|reviews/agent|characters/state_patches|drafts/promotions|branch_manifest|roleplay_simulation)\b",
}


def delivery_trace_hits(path: Path) -> list[str]:
    text = read_text(path)
    return [label for label, pattern in DELIVERY_TRACE_PATTERNS.items() if re.search(pattern, text)]


def read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {_rel(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def static_review_conclusion(path: Path) -> str:
    text = read_text(path)
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""


def approval_record_for_run(root: Path, run_id: str) -> dict[str, object]:
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
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


__all__ = [
    "approval_record_for_run",
    "delivery_trace_hits",
    "read_optional_json",
    "read_text",
    "static_review_conclusion",
    "to_int",
    "unique",
]
