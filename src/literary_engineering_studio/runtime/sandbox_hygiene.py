"""Deterministic cleanup of Agent mutations outside declared outputs."""

from __future__ import annotations

import json
from pathlib import Path

from .sandbox import (
    SandboxManifest,
    _agent_workspace,
    _control_workspace,
    _copy_path,
    _path_digest,
    _remove_path,
    _unexpected_changes,
    _workspace_hashes,
)


def restore_unexpected_agent_changes(
    sandbox: SandboxManifest,
) -> tuple[str, ...]:
    """Restore non-output files from the isolated control workspace.

    Existing files are restored only when the control copy matches the staged
    baseline. Files created after staging are removed. Anything that cannot be
    proven restorable remains visible to the fail-closed preflight.
    """

    baseline = json.loads(
        sandbox.baseline_path.read_text(encoding="utf-8")
    )
    workspace = _agent_workspace(sandbox)
    current = _workspace_hashes(workspace)
    unexpected = _unexpected_changes(
        baseline,
        current,
        sandbox.expected_outputs,
    )
    restored: list[str] = []
    for relative in unexpected:
        target = workspace / Path(relative)
        expected_digest = str(baseline.get(relative) or "")
        if not expected_digest:
            _remove_path(target)
            restored.append(relative)
            continue
        source = _control_workspace(sandbox) / Path(relative)
        if (
            not source.is_file()
            or _path_digest(source) != expected_digest
        ):
            continue
        _remove_path(target)
        _copy_path(source, target)
        restored.append(relative)
    return tuple(restored)


__all__ = ["restore_unexpected_agent_changes"]
