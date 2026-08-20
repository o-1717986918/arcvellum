"""Declared repair-target change verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue


SUPPORTED_REPAIR_STATES = {
    ("source-ingest", "extraction-review"),
    ("longform-planning", "budget-review"),
    ("longform-planning", "scene-inventory-review"),
    ("longform-planning", "chapter-obligation-review"),
    ("review-and-audit", "canon-patch-revision"),
    ("style-engineering", "style-eval-revision"),
}


def validate_source_extraction_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    if (task.route, task.current_state) not in SUPPORTED_REPAIR_STATES:
        return
    targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
    if targets and _any_declared_target_changed(task, sandbox, targets):
        return
    issues.append(
        PreflightIssue(
            "declared-repair-target-unchanged",
            "repair_targets",
            "返工没有修改任何声明的候选文件。",
            "按 review 修订至少一个候选文件；不能只把审查结论改成 pass。",
        )
    )


def _any_declared_target_changed(
    task: TaskPackage,
    sandbox: SandboxManifest,
    targets: list[str],
) -> bool:
    before = task.payload.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    for target in targets:
        path = sandbox.workspace / Path(target)
        if not path.is_file():
            continue
        previous = str(hashes.get(target) or "")
        if previous and hashlib.sha256(path.read_bytes()).hexdigest() != previous:
            return True
    return False
