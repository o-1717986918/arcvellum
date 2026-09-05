"""Shared values and path helpers for platform task writers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ..asset_workshop import ASSET_TYPES


@dataclass(frozen=True)
class PlatformAgentTaskResult:
    task_path: Path
    expected_report_path: Path
    expected_json_path: Path


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def extend_unique(target: list[Path], paths: list[Path]) -> None:
    seen = {path.resolve() for path in target if path.exists()}
    for path in paths:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        target.append(path)
        seen.add(resolved)


def style_source_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        paths.append(active)
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for key in ("prompt", "style_skill", "mount_path"):
            value = str(payload.get(key) or "").strip()
            if not value:
                continue
            candidate = root / value
            if candidate.is_dir():
                for name in (
                    "prompt.md",
                    "style_skill.json",
                    "style-profile.md",
                    "style_metrics.json",
                ):
                    child = candidate / name
                    if child.exists():
                        paths.append(child)
            elif candidate.exists():
                paths.append(candidate)
    paths.extend(
        path
        for path in (
            root / "style" / "style_prompt.md",
            root / "style" / "demo-author" / "style_prompt.md",
            root / "style" / "style-profile.md",
        )
        if path.exists()
    )
    unique: list[Path] = []
    extend_unique(unique, paths)
    return unique


def normalize_asset_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "background": "background-story",
        "background_story": "background-story",
        "relationships": "relationship",
        "world-rules": "world",
        "chapter": "chapter-plan",
        "scenes": "scene-list",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ASSET_TYPES:
        raise ValueError(f"unknown asset type: {value}. valid: {', '.join(ASSET_TYPES)}")
    return normalized


def asset_candidate_id(asset_type: str, seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{asset_type}-{slug(seed)[:28]}-platform-agent-{stamp}"


def slug(value: str) -> str:
    text = re.sub(
        r"[^A-Za-z0-9\u4e00-\u9fff]+",
        "-",
        str(value).strip(),
    ).strip("-")
    return text or "asset"


def resolve_optional(root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else root / path


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def safe_label(value: str) -> str:
    return re.sub(
        r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+",
        "-",
        value.strip(),
    ).strip("-") or "task"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


__all__ = [
    "PlatformAgentTaskResult",
    "asset_candidate_id",
    "extend_unique",
    "normalize_asset_type",
    "read_optional",
    "relative_path",
    "resolve_optional",
    "safe_label",
    "stamp",
    "style_source_paths",
]
