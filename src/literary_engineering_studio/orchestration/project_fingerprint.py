"""Stable fingerprint of planning truth, excluding plan-produced scene artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


_PLANNING_ROOTS = (
    "project.yaml",
    "canon",
    "characters",
    "plot",
    "scenes",
    "style",
    "workflow/studio/user_directions.md",
)
_EXCLUDED_PARTS = {
    "__pycache__",
    "candidates",
    "patches",
    "state_patches",
    "task_runs",
    "worker_runs",
}


def planning_project_fingerprint(project_root: Path) -> str:
    """Hash the facts a scene plan was based on, not its generated evidence."""

    root = project_root.expanduser().resolve()
    manifest: dict[str, str] = {}
    for relative in _PLANNING_ROOTS:
        target = root / relative
        candidates = (
            (target,)
            if target.is_file()
            else tuple(sorted(item for item in target.rglob("*") if item.is_file()))
            if target.is_dir()
            else ()
        )
        for path in candidates:
            rel = path.relative_to(root)
            if any(part.lower() in _EXCLUDED_PARTS for part in rel.parts):
                continue
            manifest[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    rendered = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
