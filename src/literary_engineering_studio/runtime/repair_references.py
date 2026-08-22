"""Exact source references exposed only to eligible repair turns."""

from __future__ import annotations

from pathlib import Path

from ..contracts import TaskPackage
from ..preflight.common import PreflightIssue


def repair_reference_paths(
    task: TaskPackage,
    issues: tuple[PreflightIssue, ...],
    workspace: Path,
) -> tuple[str, ...]:
    needs_exact_source = any(_needs_exact_source(issue) for issue in issues)
    if not needs_exact_source:
        return ()
    source = str(task.payload.get("revision_source") or "").strip().replace("\\", "/")
    if not _safe_relative(source):
        return ()
    authorized = {
        str(item).strip().replace("\\", "/")
        for key in ("agent_source_paths", "source_paths", "context_must_inline_paths")
        for item in (task.payload.get(key) or [])
        if str(item).strip()
    }
    if source not in authorized or not (workspace / Path(source)).is_file():
        return ()
    return (source,)


def _needs_exact_source(issue: PreflightIssue) -> bool:
    description = f"{issue.message} {issue.repair}"
    folded = description.casefold()
    return (
        "anti_evasion_rows" in description
        or "exact-source" in folded
        or "exact source body" in folded
    )


def _safe_relative(source: str) -> bool:
    return bool(
        source
        and not source.startswith("/")
        and ":" not in source
        and ".." not in source.split("/")
    )


__all__ = ["repair_reference_paths"]
