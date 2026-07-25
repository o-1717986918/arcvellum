"""Human-facing display helpers for work-project artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .draft_text import final_body_from_workbench_text
from .text_counts import count_chinese_content_chars, count_nonspace_chars


ENGINEERING_LINE_RE = re.compile(
    r"(?i)(AGENT_TASK|workflow|prompt manifest|context packet|canon notes?|state patch|writeback|"
    r"scene[_-]?\d{1,6}|chapter[_-]?\d{1,6}|\.agent_tasks\.md|\.agent_completion\.json)"
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def read_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_tail(path: Path, limit: int = 20) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def markdown_to_display_text(text: str, *, limit: int = 1200) -> str:
    """Strip common workbench/Markdown noise while preserving readable prose."""

    text = HTML_COMMENT_RE.sub("", text)
    text = CODE_FENCE_RE.sub("", text)
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if ENGINEERING_LINE_RE.search(line):
            continue
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s{0,3}[-*+]\s+", "", line)
        line = re.sub(r"^\s{0,3}\d+[.)、]\s+", "", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = line.strip()
        if line:
            lines.append(line)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return truncate_text(cleaned, limit)


def prose_body_for_display(text: str, *, limit: int = 5000) -> str:
    body = final_body_from_workbench_text(text)
    if not body:
        body = markdown_to_display_text(text, limit=limit)
    return markdown_to_display_text(body, limit=limit)


def summarize_text(text: str, *, limit: int = 180) -> str:
    plain = markdown_to_display_text(text, limit=max(limit * 3, 600))
    plain = re.sub(r"\s+", " ", plain).strip()
    return truncate_text(plain, limit)


def truncate_text(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def scalar_from_yaml_text(text: str, key: str, default: str = "") -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*:[ \t]*(.*?)[ \t]*(?:#.*)?$", text)
    if not match:
        return default
    value = match.group(1).strip()
    if value in {"", "[]", "{}", "null", "None"}:
        return default
    return value.strip("\"'")


def nested_scalar_from_yaml_text(text: str, parent: str, key: str, default: str = "") -> str:
    body = "\n".join(_yaml_block_lines(text, parent))
    if not body:
        return default
    return scalar_from_yaml_text(body, key, default)


def list_from_yaml_text(text: str, key: str, *, limit: int = 8) -> list[str]:
    inline = re.search(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*:[ \t]*\[(.*?)\][ \t]*(?:#.*)?$", text)
    if inline:
        items = [item.strip().strip("\"'") for item in inline.group(1).split(",")]
        return [item for item in items if item][:limit]
    values = []
    for line in _yaml_block_lines(text, key):
        match = re.match(r"^[ \t]*-[ \t]+(.*)$", line)
        if not match:
            continue
        item = match.group(1).strip().strip("\"'")
        if item:
            values.append(item)
    return values[:limit]


def _yaml_block_lines(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    header = re.compile(rf"^(?P<indent>[ \t]*){re.escape(key)}[ \t]*:[ \t]*(?:#.*)?$")
    for index, line in enumerate(lines):
        match = header.match(line)
        if not match:
            continue
        parent_indent = len(match.group("indent").expandtabs(4))
        body: list[str] = []
        for candidate in lines[index + 1:]:
            if not candidate.strip():
                body.append(candidate)
                continue
            indent = len(candidate) - len(candidate.lstrip(" \t"))
            if indent <= parent_indent:
                break
            body.append(candidate)
        return body
    return []


def file_label(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return stem or path.name


def display_counts(text: str, *, target: int = 0) -> dict[str, object]:
    return {
        "chinese_content_chars": count_chinese_content_chars(text),
        "machine_nonspace_chars": count_nonspace_chars(text),
        "target_chinese_content_chars": max(0, int(target or 0)),
    }
