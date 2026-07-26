"""Bounded deterministic text statistics, lookup, and search."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from ..context import CapabilityContext
from ..contracts import HandlerOutput


TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv", ".html", ".xml", ".ini", ".cfg"}
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_SEARCH_FILES = 256
HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
PUNCTUATION_PATTERN = re.compile(r"[，。！？；：、“”‘’（）《》〈〉【】……—,.!?;:'\"()\[\]{}]")


def text_statistics(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    relative = str(arguments.get("path") or "")
    text, path = _read_text(context, relative, scope=str(arguments.get("scope") or "auto"))
    data = {
        "path": relative,
        "bytes": path.stat().st_size,
        "machine_characters": len(text),
        "non_whitespace_characters": sum(not char.isspace() for char in text),
        "han_characters": len(HAN_PATTERN.findall(text)),
        "punctuation_characters": len(PUNCTUATION_PATTERN.findall(text)),
        "lines": len(text.splitlines()),
        "paragraphs": len([item for item in re.split(r"\n\s*\n", text) if item.strip()]),
    }
    return HandlerOutput(f"text statistics completed: {relative}", data)


def reference_search(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    query = str(arguments.get("query") or "").strip()
    if not query or len(query) > 120:
        raise ValueError("reference.search query must contain 1-120 characters")
    max_results = _bounded_int(arguments.get("max_results"), default=20, minimum=1, maximum=50)
    paths = _requested_paths(arguments.get("paths"), context.manifest.readable_paths)
    matches: list[dict[str, object]] = []
    needle = query.casefold()
    for relative, path in _iter_text_files(context, paths):
        for number, line in enumerate(_read_bounded(path).splitlines(), start=1):
            if needle not in line.casefold():
                continue
            matches.append({"path": relative, "line": number, "snippet": _snippet(line, query)})
            if len(matches) >= max_results:
                return HandlerOutput(
                    f"reference search found at least {len(matches)} matches",
                    {"query": query, "matches": matches, "limit_reached": True},
                )
    return HandlerOutput(
        f"reference search found {len(matches)} matches",
        {"query": query, "matches": matches, "limit_reached": False},
    )


def citation_lookup(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    citation_id = str(arguments.get("citation_id") or "").strip()
    if not citation_id or len(citation_id) > 160:
        raise ValueError("citation_id must contain 1-160 characters")
    defaults = [
        path
        for path in context.manifest.readable_paths
        if any(token in Path(path).name.lower() for token in ("evidence", "citation", "source"))
    ]
    paths = _requested_paths(arguments.get("paths"), defaults or context.manifest.readable_paths)
    matches: list[dict[str, object]] = []
    needle = citation_id.casefold()
    for relative, path in _iter_text_files(context, paths):
        for number, line in enumerate(_read_bounded(path).splitlines(), start=1):
            if needle not in line.casefold():
                continue
            matches.append({"path": relative, "line": number, "snippet": _snippet(line, citation_id, radius=220)})
            if len(matches) >= 20:
                break
        if len(matches) >= 20:
            break
    return HandlerOutput(
        f"citation lookup found {len(matches)} references",
        {"citation_id": citation_id, "matches": matches, "limit_reached": len(matches) >= 20},
    )


def _requested_paths(value: object, defaults: Iterable[str]) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys(str(item) for item in value if str(item).strip()))
    return list(dict.fromkeys(defaults))


def _iter_text_files(context: CapabilityContext, paths: list[str]):
    count = 0
    for relative in paths:
        path = context.resolve_path(relative)
        candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in TEXT_SUFFIXES:
                continue
            count += 1
            if count > MAX_SEARCH_FILES:
                return
            try:
                item_rel = candidate.relative_to(context.workspace_root.resolve()).as_posix() if context.workspace_root and candidate.is_relative_to(context.workspace_root.resolve()) else candidate.relative_to(context.task.project_root).as_posix()
            except ValueError:
                item_rel = relative
            yield item_rel, candidate


def _read_text(context: CapabilityContext, relative: str, *, scope: str) -> tuple[str, Path]:
    path = context.resolve_path(relative, scope=scope)
    if not path.is_file():
        raise FileNotFoundError(f"capability text source not found: {relative}")
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError(f"capability supports UTF-8 text files only: {relative}")
    return _read_bounded(path), path


def _read_bounded(path: Path) -> str:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"text source exceeds {MAX_SOURCE_BYTES} bytes")
    return path.read_text(encoding="utf-8")


def _snippet(line: str, query: str, *, radius: int = 140) -> str:
    compact = " ".join(line.strip().split())
    index = compact.casefold().find(query.casefold())
    if index < 0:
        return compact[: radius * 2]
    start = max(0, index - radius)
    end = min(len(compact), index + len(query) + radius)
    return ("…" if start else "") + compact[start:end] + ("…" if end < len(compact) else "")


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))
