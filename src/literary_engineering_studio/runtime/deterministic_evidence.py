"""Refresh system-owned evidence after bounded project revisions."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..core_bridge import CoreBridge


CANON_LINT_PATHS = ("reviews/canon_lint.md", "reviews/canon_lint.json")
LONGFORM_AUDIT_PATHS = (
    "reviews/longform/longform_audit.md",
    "reviews/longform/longform_audit.json",
    "reviews/longform/longform_graph.json",
)


def refresh_deterministic_evidence(
    bridge: CoreBridge,
    task: TaskPackage,
    project_root: Path,
) -> tuple[str, ...]:
    """Rebuild evidence invalidated by one formal revision task.

    These files are produced by the Engine, never by the Agent.  The caller
    owns transaction rollback and invokes this function again after restoring
    project sources so evidence and formal files always describe one snapshot.
    """

    state = task.current_state
    refreshed: list[str] = []
    if state in {"canon-review-pass", "committee-pass"}:
        bridge.run(["canon-lint", str(project_root.resolve())]).require_success()
        refreshed.extend(CANON_LINT_PATHS)
    if state == "committee-pass":
        bridge.run(
            [
                "longform-audit",
                str(project_root.resolve()),
                "--target-length",
                str(project_target_length(project_root)),
            ],
            timeout=600,
        ).require_success()
        refreshed.extend(LONGFORM_AUDIT_PATHS)
    return tuple(refreshed)


def project_target_length(project_root: Path) -> int:
    """Read the project's formal Chinese-content target for audit replay."""

    budget = _read_json(project_root / "plot" / "word_budget" / "word_budget.json")
    for container_name in ("target", "totals"):
        container = budget.get(container_name)
        if not isinstance(container, dict):
            continue
        for field in ("target_chinese_chars", "target_words"):
            value = _positive_int(container.get(field))
            if value:
                return value

    audit = _read_json(
        project_root / "reviews" / "longform" / "longform_audit.json"
    )
    summary = audit.get("summary")
    if isinstance(summary, dict):
        value = _positive_int(summary.get("target_length"))
        if value:
            return value
    return 100_000


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _positive_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


__all__ = [
    "CANON_LINT_PATHS",
    "LONGFORM_AUDIT_PATHS",
    "project_target_length",
    "refresh_deterministic_evidence",
]
