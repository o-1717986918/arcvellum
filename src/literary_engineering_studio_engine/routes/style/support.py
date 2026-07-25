"""Small route-neutral helpers shared by the style route definition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...task_paths import relative_path, resolve_project_path


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
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def declared_repair_targets_changed(
    root: Path,
    task: dict[str, object],
    label: str,
) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    hashes = task.get("repair_target_sha256_before_revision")
    before = hashes if isinstance(hashes, dict) else {}
    if not targets or not before:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = resolve_project_path(root, target)
        previous = str(before.get(target) or "").strip().lower()
        if path.is_file() and previous and file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]
