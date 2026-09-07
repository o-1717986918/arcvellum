"""Safely restore user-readable artifact content after reconnecting Creative Live."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .artifact_projection import MAX_ACTIVE_ARTIFACT_CHARS


_DISPLAYABLE_SUFFIXES = frozenset({".md", ".txt"})
_MACHINE_MARKERS = (
    ".agent_completion.",
    ".agent_tasks.",
    ".trace.",
    ".manifest.",
    ".receipt.",
)


def hydrate_presentable_artifacts(
    project_root: str | Path,
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return displayable artifacts, restoring blank content from safe project files."""
    root = Path(project_root).resolve()
    visible: list[dict[str, Any]] = []
    for artifact in artifacts:
        relative = str(artifact.get("path") or "").replace("\\", "/")
        if not _is_presentable(relative):
            continue
        item = dict(artifact)
        if not str(item.get("content") or ""):
            content = _read_current_content(root, relative, str(item.get("digest") or ""))
            if content is not None:
                item["content"] = content[:MAX_ACTIVE_ARTIFACT_CHARS]
                item["characters"] = len(content)
                item["truncated"] = len(content) > MAX_ACTIVE_ARTIFACT_CHARS
        visible.append(item)
    return visible


def _is_presentable(relative: str) -> bool:
    normalized = relative.casefold()
    if not relative or Path(relative).suffix.casefold() not in _DISPLAYABLE_SUFFIXES:
        return False
    return not any(marker in normalized for marker in _MACHINE_MARKERS)


def _read_current_content(root: Path, relative: str, expected_digest: str) -> str | None:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    if not candidate.is_file() or candidate.stat().st_size > MAX_ACTIVE_ARTIFACT_CHARS * 4:
        return None
    payload = candidate.read_bytes()
    digest = _normalized_digest(expected_digest)
    if digest and hashlib.sha256(payload).hexdigest() != digest:
        return None
    try:
        return payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        return None


def _normalized_digest(value: str) -> str:
    normalized = value.removeprefix("sha256:").casefold()
    if len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized):
        return normalized
    return ""


__all__ = ["hydrate_presentable_artifacts"]
