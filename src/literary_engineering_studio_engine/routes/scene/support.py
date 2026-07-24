"""Shared parsing and provenance helpers for scene route definitions."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from ...task_paths import relative_path as _rel


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _read_optional_json(path: Path) -> tuple[dict[str, object], str]:
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _static_review_conclusion(path: Path) -> str:
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", _read_text(path), re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _context_source_paths(root: Path, scene_rel: str) -> list[str]:
    hard_context = [
        "project.yaml", scene_rel, "canon", "characters", "plot/outline.md",
        "plot/foreshadowing.csv", "plot/conflict_matrix.md", "plot/word_budget/word_budget.json",
        "plot/word_budget/word_budget.md", "plot/chapter_obligations", "plot/rhythm_plan.json",
        "workflow/longform_materialization.json", "style",
    ]
    index = root / "memory" / "index.json"
    hard_context.extend(["memory/index.json"] if index.is_file() else ["sources", "scenes", "drafts/scenes", "reviews/agent"])
    return [rel for rel in dict.fromkeys(hard_context) if (root / rel).exists()]


def _project_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    return "" if value in {"null", "[]", "{}"} else value.strip("\"'")


def _project_int(text: str, key: str) -> int:
    return _to_int(_project_scalar(text, key))


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
