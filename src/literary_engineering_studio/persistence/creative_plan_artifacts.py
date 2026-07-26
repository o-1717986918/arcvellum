"""Physical artifact checks required before a plan revision becomes ready."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any


AUDIT_REFERENCE_FIELDS = (
    "candidate",
    "normalized",
    "compiled",
    "lint",
    "simulation",
    "review",
)


def verify_indexed_plan_artifacts(
    project_root: str,
    revision: dict[str, Any],
) -> None:
    root = Path(project_root).expanduser().resolve()
    for field in AUDIT_REFERENCE_FIELDS:
        reference = revision.get(field)
        if not isinstance(reference, dict):
            raise RuntimeError(f"creative plan audit reference is missing: {field}")
        relative = _safe_relative_path(reference.get("path"))
        target = (root / relative).resolve()
        if root not in target.parents:
            raise RuntimeError("creative plan audit path escapes the work project")
        if not target.is_file():
            raise RuntimeError(
                f"creative plan audit file is missing: {relative.as_posix()}"
            )
        observed = hashlib.sha256(target.read_bytes()).hexdigest()
        if observed != str(reference.get("sha256") or ""):
            raise RuntimeError(
                f"creative plan audit file digest mismatch: {relative.as_posix()}"
            )


def _safe_relative_path(value: object) -> PurePosixPath:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise RuntimeError(f"invalid creative plan audit path: {value}")
    return path
