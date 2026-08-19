"""Determine the smallest coherent write scope for a repair turn."""

from __future__ import annotations

from ..contracts import TaskPackage
from ..preflight.common import PreflightIssue


_SCENE_REVISION_STATES = frozenset({"candidate-revision", "static-revision"})


def agent_writable_outputs(task: TaskPackage) -> tuple[str, ...]:
    """Return task outputs owned by the Agent rather than the control plane."""

    core = set(task.core_managed_outputs)
    completion = {
        item.path
        for item in task.execution_contract.outputs
        if item.kind == "completion-evidence"
    }
    return tuple(
        path
        for path in task.expected_outputs
        if path not in core and path not in completion
    )


def repair_scope(
    task: TaskPackage,
    issues: tuple[PreflightIssue, ...],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Select repair targets while preserving semantic output dependencies."""

    writable = agent_writable_outputs(task)
    targets = list(_issue_targets(issues, writable))
    for dependent in _coupled_targets(task, issues, writable):
        if dependent not in targets:
            targets.append(dependent)
    if targets:
        mode = "targeted"
    else:
        targets = list(writable)
        mode = "all_declared_outputs_fallback"
    target_set = set(targets)
    protected = tuple(path for path in writable if path not in target_set)
    return mode, tuple(targets), protected


def _issue_targets(
    issues: tuple[PreflightIssue, ...],
    writable: tuple[str, ...],
) -> tuple[str, ...]:
    allowed = set(writable)
    targets: list[str] = []
    for issue in issues:
        relative = issue.path.partition("#")[0]
        if relative in allowed and relative not in targets:
            targets.append(relative)
    return tuple(targets)


def _coupled_targets(
    task: TaskPackage,
    issues: tuple[PreflightIssue, ...],
    writable: tuple[str, ...],
) -> tuple[str, ...]:
    """Expand semantic revisions to the candidate/manifest transaction pair."""

    if task.current_state not in _SCENE_REVISION_STATES:
        return ()
    issue_paths = tuple(issue.path.partition("#")[0] for issue in issues)
    if not (
        any(issue.code == "scene-revision-invalid" for issue in issues)
        or any(_is_revision_transaction_output(path) for path in issue_paths)
    ):
        return ()
    return tuple(path for path in writable if _is_revision_transaction_output(path))


def _is_revision_transaction_output(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if not normalized.startswith("drafts/revisions/"):
        return False
    name = normalized.rsplit("/", 1)[-1]
    if not (name.endswith(".md") or name.endswith(".json")):
        return False
    stem = name.rsplit(".", 1)[0]
    suffix = stem.rpartition("_revision")[2]
    return "_revision" in stem and (not suffix or suffix.startswith("_") and suffix[1:].isdigit())
