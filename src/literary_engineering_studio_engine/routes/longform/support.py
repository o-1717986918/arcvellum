"""Route-local deterministic helpers for longform planning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from ...task_paths import relative_path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {relative_path(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    return (payload, "") if isinstance(payload, dict) else ({}, f"JSON root is not an object: {path}")


def static_review_conclusion(path: Path) -> str:
    text = read_text(path).strip()
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def project_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")


def project_int(text: str, key: str) -> int:
    return to_int(project_scalar(text, key))


def to_int(value: object) -> int:
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


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))

