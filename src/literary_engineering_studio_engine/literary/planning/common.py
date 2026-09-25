"""Shared data and path primitives for long-form word-budget planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

GENRE_PRESETS = {
    "general": {
        "label": "通用长篇",
        "aliases": {"general", "novel", "通用", "小说", "长篇"},
        "chapter_words": 4000,
        "scene_words": 1400,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
    },
    "mystery": {
        "label": "悬疑/推理",
        "aliases": {"mystery", "suspense", "thriller", "悬疑", "推理", "惊悚"},
        "chapter_words": 3800,
        "scene_words": 1250,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
    },
    "speculative": {
        "label": "科幻/奇幻/玄幻",
        "aliases": {"speculative", "fantasy", "sci-fi", "science-fiction", "科幻", "奇幻", "玄幻"},
        "chapter_words": 4200,
        "scene_words": 1500,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
    },
    "urban": {
        "label": "都市/职场/现实",
        "aliases": {"urban", "workplace", "realist", "都市", "职场", "现实"},
        "chapter_words": 3600,
        "scene_words": 1200,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
    },
    "literary": {
        "label": "文学向",
        "aliases": {"literary", "literature", "文学", "严肃文学"},
        "chapter_words": 4500,
        "scene_words": 1600,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
    },
}


@dataclass(frozen=True)
class WordBudgetResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    agent_tasks_path: Path
    scene_inventory_tasks_path: Path
    chapter_obligation_tasks_path: Path
    target_words: int
    volume_count: int
    chapter_count: int
    scene_count: int
    status: str
    issue_count: int

def _project_int(project_text: str, key: str) -> int:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(\d+)", project_text)
    return int(match.group(1)) if match else 0

def _project_genre(project_text: str) -> str:
    match = re.search(r"(?m)^[ \t]*genre:[ \t]*(.*?)\s*$", project_text)
    return match.group(1).strip().strip("\"'") if match else ""

def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")

def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path

def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""

def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}

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

def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
