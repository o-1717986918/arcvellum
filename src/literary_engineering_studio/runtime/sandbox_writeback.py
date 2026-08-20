"""Expected-output-only preview, import, and rollback transaction."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Callable, Iterable

from ..contracts import OutputContract, TaskPackage
from .run_manifest import update_run_manifest
from .sandbox_contracts import SandboxManifest
from .sandbox_files import (
    agent_workspace,
    control_workspace,
    copy_path,
    copy_path_atomically,
    path_digest,
    path_size,
    readable_diff,
    remove_path,
    utc_now,
)
from .writeback_contracts import WritebackPreview


ChangeIssueProvider = Callable[[SandboxManifest], list[str]]


def sync_agent_outputs_to_control(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> tuple[str, ...]:
    """Copy only declared Agent outputs into the deterministic control view."""
    if task.execution_contract.execution_policy != "agent-required":
        return ()
    imported: list[str] = []
    for relative in task.expected_outputs:
        source = agent_workspace(sandbox) / Path(relative)
        if not source.exists():
            continue
        copy_path(source, control_workspace(sandbox) / Path(relative))
        imported.append(relative)
    update_run_manifest(
        sandbox.manifest_path,
        agent_outputs_staged_to_control=imported,
    )
    return tuple(imported)


def control_sandbox_view(sandbox: SandboxManifest) -> SandboxManifest:
    """Return a preflight view rooted at the deterministic control workspace."""
    return replace(sandbox, workspace=control_workspace(sandbox))


def inspect_expected_outputs(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    change_issues: ChangeIssueProvider,
) -> WritebackPreview:
    issues = change_issues(sandbox)
    if issues:
        raise ValueError(issues[0])
    sync_agent_outputs_to_control(task, sandbox)
    workspace = control_workspace(sandbox)
    missing = [
        relative
        for relative in sandbox.expected_outputs
        if not (workspace / Path(relative)).exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Agent runtime did not create expected outputs: " + ", ".join(missing)
        )

    contracts = {item.path: item for item in task.execution_contract.outputs}
    changes = tuple(
        _output_change(task, workspace, relative, contracts.get(relative))
        for relative in sandbox.expected_outputs
    )
    preview_path = sandbox.run_root / "writeback.preview.json"
    payload = {
        "schema": "literary-engineering-studio/writeback-preview/v0.1",
        "task_id": task.task_id,
        "project_root": str(task.project_root),
        "policy": task.execution_contract.writeback_policy,
        "created_at": utc_now(),
        "changes": list(changes),
    }
    preview_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_preview_ready",
        writeback_policy=task.execution_contract.writeback_policy,
        writeback_preview=str(preview_path),
    )
    return WritebackPreview(
        task.execution_contract.writeback_policy,
        preview_path,
        changes,
    )


def _output_change(
    task: TaskPackage,
    workspace: Path,
    relative: str,
    contract: OutputContract | None,
) -> dict[str, object]:
    source = workspace / Path(relative)
    target = task.resolve_project_path(relative)
    return {
        "path": relative,
        "kind": contract.kind if contract else "agent-authored",
        "writeback_policy": (
            contract.writeback_policy if contract else "preview-required"
        ),
        "change_type": "modified" if target.exists() else "created",
        "before_sha256": path_digest(target),
        "after_sha256": path_digest(source),
        "before_bytes": path_size(target),
        "after_bytes": path_size(source),
        "diff": readable_diff(target, source, relative),
    }


def apply_expected_outputs(
    task: TaskPackage,
    sandbox: SandboxManifest,
    preview: WritebackPreview,
) -> tuple[str, ...]:
    _reject_stale_targets(task, preview)
    backup_index = _prepare_backups(task, sandbox)
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_prepared",
        writeback_transaction={
            "state": "prepared",
            "backup_index": str(sandbox.run_root / "backups" / "index.json"),
            "outputs": backup_index,
        },
    )
    imported: list[str] = []
    try:
        for relative in sandbox.expected_outputs:
            copy_path_atomically(
                control_workspace(sandbox) / Path(relative),
                task.resolve_project_path(relative),
            )
            imported.append(relative)
    except Exception as exc:
        rollback_expected_outputs(task, sandbox, imported)
        update_run_manifest(
            sandbox.manifest_path,
            status="writeback_import_failed",
            writeback_transaction={
                "state": "rolled_back_after_import_failure",
                "error": str(exc),
                "imported_outputs": imported,
            },
        )
        raise
    update_run_manifest(
        sandbox.manifest_path,
        status="outputs_imported",
        imported_outputs=imported,
        writeback_transaction={"state": "imported", "imported_outputs": imported},
    )
    return tuple(imported)


def _reject_stale_targets(task: TaskPackage, preview: WritebackPreview) -> None:
    for change in preview.changes:
        relative = str(change["path"])
        if path_digest(task.resolve_project_path(relative)) != str(
            change.get("before_sha256") or ""
        ):
            raise RuntimeError(
                f"formal project changed after writeback preview: {relative}"
            )


def _prepare_backups(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, object]]:
    backup_root = sandbox.run_root / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_index: list[dict[str, object]] = []
    for relative in sandbox.expected_outputs:
        target = task.resolve_project_path(relative)
        existed = target.exists()
        if existed:
            copy_path(target, backup_root / Path(relative))
        backup_index.append(
            {
                "path": relative,
                "existed": existed,
                "before_sha256": path_digest(target),
            }
        )
    (backup_root / "index.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-studio/writeback-backup/v0.2",
                "task_id": task.task_id,
                "created_at": utc_now(),
                "outputs": backup_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return backup_index


def import_expected_outputs(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    change_issues: ChangeIssueProvider,
) -> tuple[str, ...]:
    preview = inspect_expected_outputs(task, sandbox, change_issues=change_issues)
    return apply_expected_outputs(task, sandbox, preview)


def rollback_expected_outputs(
    task: TaskPackage,
    sandbox: SandboxManifest,
    imported: Iterable[str],
) -> None:
    backup_root = sandbox.run_root / "backups"
    restored = list(imported)
    for relative in restored:
        target = task.resolve_project_path(relative)
        backup = backup_root / Path(relative)
        remove_path(target)
        if backup.exists():
            copy_path_atomically(backup, target)
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_rolled_back",
        writeback_transaction={"state": "rolled_back", "outputs": restored},
    )


def load_writeback_preview(run_root: Path) -> WritebackPreview:
    path = run_root.expanduser().resolve() / "writeback.preview.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise ValueError(f"invalid writeback preview: {path}")
    return WritebackPreview(
        str(payload.get("policy") or "preview-required"),
        path,
        tuple(item for item in changes if isinstance(item, dict)),
    )


__all__ = [
    "apply_expected_outputs",
    "control_sandbox_view",
    "import_expected_outputs",
    "inspect_expected_outputs",
    "load_writeback_preview",
    "rollback_expected_outputs",
    "sync_agent_outputs_to_control",
]
