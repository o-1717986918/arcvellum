"""Per-task isolated workspaces and expected-output-only writeback."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Iterable

from literary_engineering_studio_engine.resources import engine_root

from ..contracts import TaskPackage
from ..task_program import compact_task_references, render_worker_program, write_task_context


MANIFEST_SCHEMA = "literary-engineering-studio/task-sandbox/v0.1"
IGNORED_RUNTIME_PATHS = {"AGENT_TASK.md", "_task", ".claude", ".codex", ".git"}


@dataclass(frozen=True)
class SandboxManifest:
    run_id: str
    run_root: Path
    # ``workspace`` remains the Agent-visible workspace for compatibility with
    # runtimes and existing run links.  The control workspace is never handed
    # to a model; it exists solely for formal CLI commands and preflight.
    workspace: Path
    prompt_path: Path
    manifest_path: Path
    baseline_path: Path
    expected_outputs: tuple[str, ...]
    control_workspace: Path | None = None
    agent_workspace: Path | None = None


@dataclass(frozen=True)
class WritebackPreview:
    policy: str
    preview_path: Path
    changes: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "literary-engineering-studio/writeback-preview/v0.1",
            "policy": self.policy,
            "preview_path": str(self.preview_path),
            "change_count": len(self.changes),
            "changes": list(self.changes),
        }


def stage_task(
    task: TaskPackage,
    runs_root: Path,
    *,
    runtime: str,
    run_id: str | None = None,
) -> SandboxManifest:
    identifier = run_id or _run_id(task.task_id)
    project_key = _project_key(task.project_root)
    run_root = runs_root.expanduser().resolve() / project_key / identifier
    if run_root.exists():
        raise FileExistsError(f"Studio run already exists: {run_root}")
    workspace = run_root / "workspace"
    control_workspace = run_root / "control-workspace"
    control_workspace.mkdir(parents=True, exist_ok=False)

    copied_sources: list[str] = []
    missing_sources: list[str] = []
    reference_paths = compact_task_references(task)
    agent_sources = task.payload.get("agent_source_paths")
    agent_sources = [str(item) for item in agent_sources] if isinstance(agent_sources, list) else []
    # The control workspace must be able to run the exact CLI command and the
    # exact deterministic preflight.  It intentionally receives the full task
    # dependency set.  The Agent sees a separately materialized workspace
    # below, containing only its explicit reading contract.
    staged_sources = [*reference_paths, *task.source_paths, *agent_sources]
    for relative in _unique(staged_sources):
        source = task.resolve_project_path(relative)
        if not source.exists():
            embedded = engine_root() / Path(relative)
            if embedded.exists():
                source = embedded
        if not source.exists():
            missing_sources.append(relative)
            continue
        _copy_path(source, control_workspace / Path(relative))
        copied_sources.append(relative)

    for relative in task.expected_outputs:
        source = task.resolve_project_path(relative)
        destination = control_workspace / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            _copy_path(source, destination)

    # Engine commands validate their positional project argument before they
    # inspect task-specific inputs.  Every sandbox is therefore a minimal,
    # runnable work-project rather than a bag of detached source files.  This
    # descriptor remains outside expected outputs, so an Agent cannot alter it
    # or write changes back through the task boundary.
    project_descriptor = task.project_root / "project.yaml"
    if project_descriptor.is_file():
        _copy_path(project_descriptor, control_workspace / "project.yaml")
        if "project.yaml" not in copied_sources:
            copied_sources.append("project.yaml")

    direction_digest = task.project_root / "workflow" / "studio" / "user_directions.md"
    if direction_digest.is_file():
        relative = "workflow/studio/user_directions.md"
        _copy_path(direction_digest, control_workspace / Path(relative))
        copied_sources.append(relative)

    prompt_path = workspace / "AGENT_TASK.md"
    baseline_path = run_root / "agent-baseline.json"
    manifest_path = run_root / "run.json"
    payload = {
        "schema": MANIFEST_SCHEMA,
        "run_id": identifier,
        "status": "prepared",
        "created_at": _now(),
        "runtime": runtime,
        "project_root": str(task.project_root),
        "task_id": task.task_id,
        "task_json": str(task.task_json_path),
        "task_markdown": str(task.task_markdown_path),
        "route": task.route,
        "current_state": task.current_state,
        "workspace": str(workspace),
        "control_workspace": str(control_workspace),
        "prompt": str(prompt_path),
        "copied_sources": copied_sources,
        "reference_paths": list(reference_paths),
        "omitted_reference_paths": [path for path in task.required_reading if path not in reference_paths],
        "missing_sources": missing_sources,
        "expected_outputs": list(task.expected_outputs),
        "human_gate_reasons": list(task.human_gate_reasons),
        "execution_contract": task.execution_contract.as_dict(),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sandbox = SandboxManifest(
        run_id=identifier,
        run_root=run_root,
        workspace=workspace,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        baseline_path=baseline_path,
        expected_outputs=task.expected_outputs,
        control_workspace=control_workspace,
        agent_workspace=workspace,
    )
    materialize_agent_workspace(task, sandbox)
    return sandbox


def materialize_agent_workspace(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    """Build the bounded Agent view from the fully reproducible control view."""

    workspace = _agent_workspace(sandbox)
    _remove_path(workspace)
    workspace.mkdir(parents=True, exist_ok=False)
    reference_paths = compact_task_references(task)
    agent_sources = task.payload.get("agent_source_paths")
    agent_sources = [str(item) for item in agent_sources] if isinstance(agent_sources, list) else list(task.source_paths)
    visible_paths = _unique(
        [
            *reference_paths,
            *agent_sources,
            *task.expected_outputs,
            *task.core_managed_outputs,
            "project.yaml",
            "workflow/studio/user_directions.md",
        ]
    )
    copied: list[str] = []
    missing: list[str] = []
    for relative in visible_paths:
        source = _control_workspace(sandbox) / Path(relative)
        if not source.exists():
            embedded = engine_root() / Path(relative)
            if embedded.exists():
                source = embedded
        if not source.exists():
            # Expected outputs are often intentionally created by the Agent.
            if relative not in task.expected_outputs:
                missing.append(relative)
            continue
        _copy_path(source, workspace / Path(relative))
        copied.append(relative)

    task_dir = workspace / "_task"
    task_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(task.task_json_path, task_dir / "task.json")
    shutil.copy2(task.task_markdown_path, task_dir / "task.agent_tasks.md")
    (task_dir / "execution_contract.json").write_text(
        json.dumps(task.execution_contract.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sandbox.prompt_path.write_text(_render_agent_prompt(task, reference_paths=reference_paths), encoding="utf-8")
    write_task_context(task, workspace / "TASK_CONTEXT.json", reference_paths=reference_paths)
    refresh_sandbox_baseline(sandbox)
    update_run_manifest(
        sandbox.manifest_path,
        agent_visible_paths=visible_paths,
        agent_copied_sources=copied,
        agent_missing_sources=missing,
    )
    return tuple(copied)


def refresh_sandbox_baseline(sandbox: SandboxManifest) -> None:
    """Refresh the Agent-only baseline after the bounded view is materialized."""

    baseline = _workspace_hashes(_agent_workspace(sandbox))
    sandbox.baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_run_manifest(
        sandbox.manifest_path,
        agent_baseline_refreshed_at=_now(),
        agent_baseline_file_count=len(baseline),
    )


def sync_agent_outputs_to_control(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    """Copy only declared Agent outputs back into the validation workspace."""

    if task.execution_contract.execution_policy != "agent-required":
        return ()
    imported: list[str] = []
    for relative in task.expected_outputs:
        source = _agent_workspace(sandbox) / Path(relative)
        if not source.exists():
            continue
        _copy_path(source, _control_workspace(sandbox) / Path(relative))
        imported.append(relative)
    update_run_manifest(sandbox.manifest_path, agent_outputs_staged_to_control=imported)
    return tuple(imported)


def control_sandbox_view(sandbox: SandboxManifest) -> SandboxManifest:
    """Return a preflight view whose artifact root is the control workspace."""

    return replace(sandbox, workspace=_control_workspace(sandbox))


def inspect_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> WritebackPreview:
    issues = sandbox_change_issues(sandbox)
    if issues:
        raise ValueError(
            issues[0]
        )
    sync_agent_outputs_to_control(task, sandbox)
    workspace = _control_workspace(sandbox)

    missing: list[str] = []
    for relative in sandbox.expected_outputs:
        if not (workspace / Path(relative)).exists():
            missing.append(relative)
    if missing:
        raise FileNotFoundError("Agent runtime did not create expected outputs: " + ", ".join(missing))

    contracts = {item.path: item for item in task.execution_contract.outputs}
    changes: list[dict[str, object]] = []
    for relative in sandbox.expected_outputs:
        source = workspace / Path(relative)
        target = task.resolve_project_path(relative)
        contract = contracts.get(relative)
        changes.append(
            {
                "path": relative,
                "kind": contract.kind if contract else "agent-authored",
                "writeback_policy": contract.writeback_policy if contract else "preview-required",
                "change_type": "modified" if target.exists() else "created",
                "before_sha256": _path_digest(target),
                "after_sha256": _path_digest(source),
                "before_bytes": _path_size(target),
                "after_bytes": _path_size(source),
                "diff": _readable_diff(target, source, relative),
            }
        )
    preview_path = sandbox.run_root / "writeback.preview.json"
    payload = {
        "schema": "literary-engineering-studio/writeback-preview/v0.1",
        "task_id": task.task_id,
        "project_root": str(task.project_root),
        "policy": task.execution_contract.writeback_policy,
        "created_at": _now(),
        "changes": changes,
    }
    preview_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_preview_ready",
        writeback_policy=task.execution_contract.writeback_policy,
        writeback_preview=str(preview_path),
    )
    return WritebackPreview(task.execution_contract.writeback_policy, preview_path, tuple(changes))


def apply_expected_outputs(task: TaskPackage, sandbox: SandboxManifest, preview: WritebackPreview) -> tuple[str, ...]:
    for change in preview.changes:
        relative = str(change["path"])
        target = task.resolve_project_path(relative)
        if _path_digest(target) != str(change.get("before_sha256") or ""):
            raise RuntimeError(f"formal project changed after writeback preview: {relative}")

    backup_root = sandbox.run_root / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_index: list[dict[str, object]] = []
    for relative in sandbox.expected_outputs:
        target = task.resolve_project_path(relative)
        existed = target.exists()
        backup = backup_root / Path(relative)
        if existed:
            _copy_path(target, backup)
        backup_index.append(
            {
                "path": relative,
                "existed": existed,
                "before_sha256": _path_digest(target),
            }
        )
    (backup_root / "index.json").write_text(
        json.dumps(
            {
                "schema": "literary-engineering-studio/writeback-backup/v0.2",
                "task_id": task.task_id,
                "created_at": _now(),
                "outputs": backup_index,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_prepared",
        writeback_transaction={"state": "prepared", "backup_index": str(backup_root / "index.json"), "outputs": backup_index},
    )

    imported: list[str] = []
    try:
        for relative in sandbox.expected_outputs:
            source = _control_workspace(sandbox) / Path(relative)
            target = task.resolve_project_path(relative)
            _copy_path_atomically(source, target)
            imported.append(relative)
    except Exception as exc:
        rollback_expected_outputs(task, sandbox, imported)
        update_run_manifest(
            sandbox.manifest_path,
            status="writeback_import_failed",
            writeback_transaction={"state": "rolled_back_after_import_failure", "error": str(exc), "imported_outputs": imported},
        )
        raise
    update_run_manifest(
        sandbox.manifest_path,
        status="outputs_imported",
        imported_outputs=imported,
        writeback_transaction={"state": "imported", "imported_outputs": imported},
    )
    return tuple(imported)


def import_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    preview = inspect_expected_outputs(task, sandbox)
    return apply_expected_outputs(task, sandbox, preview)


def rollback_expected_outputs(task: TaskPackage, sandbox: SandboxManifest, imported: Iterable[str]) -> None:
    backup_root = sandbox.run_root / "backups"
    restored = list(imported)
    for relative in restored:
        target = task.resolve_project_path(relative)
        backup = backup_root / Path(relative)
        _remove_path(target)
        if backup.exists():
            _copy_path_atomically(backup, target)
    update_run_manifest(
        sandbox.manifest_path,
        status="writeback_rolled_back",
        writeback_transaction={"state": "rolled_back", "outputs": restored},
    )


def _copy_path_atomically(source: Path, target: Path) -> None:
    """Replace one expected output through a same-directory staging path.

    A cross-file transaction cannot be atomic on a normal filesystem, but each
    target replacement is atomic where supported and the complete backup index
    lets the Worker restore every already-replaced path if a later step fails.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(f".{target.name}.arcvellum-write-{os.getpid()}-{datetime.now(timezone.utc).strftime('%f')}")
    _remove_path(staged)
    try:
        _copy_path(source, staged)
        _remove_path(target)
        os.replace(staged, target)
    finally:
        _remove_path(staged)


def _remove_path(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def sandbox_from_run(run_root: Path) -> SandboxManifest:
    root = run_root.expanduser().resolve()
    manifest_path = root / "run.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    workspace = Path(str(payload["workspace"])).resolve()
    control_workspace = Path(str(payload.get("control_workspace") or workspace)).resolve()
    return SandboxManifest(
        run_id=str(payload["run_id"]),
        run_root=root,
        workspace=workspace,
        prompt_path=Path(str(payload["prompt"])).resolve(),
        manifest_path=manifest_path,
        baseline_path=root / ("agent-baseline.json" if (root / "agent-baseline.json").exists() else "baseline.json"),
        expected_outputs=tuple(str(item) for item in payload.get("expected_outputs") or []),
        control_workspace=control_workspace,
        agent_workspace=workspace,
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


def capture_core_managed_outputs(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    """Snapshot deterministic command outputs before handing control to an Agent."""

    protected_root = sandbox.run_root / "core-managed"
    captured: list[str] = []
    digests: dict[str, str] = {}
    for relative in task.core_managed_outputs:
        source = _control_workspace(sandbox) / Path(relative)
        if not source.exists():
            continue
        _copy_path(source, protected_root / Path(relative))
        captured.append(relative)
        digests[relative] = _path_digest(source)
    if captured:
        update_run_manifest(
            sandbox.manifest_path,
            core_managed_outputs=captured,
            core_managed_digests=digests,
        )
    return tuple(captured)


def restore_core_managed_outputs(sandbox: SandboxManifest) -> tuple[str, ...]:
    """Restore command-owned files if a runtime tried to rewrite them."""

    payload = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
    protected = [str(item) for item in payload.get("core_managed_outputs") or []]
    protected_root = sandbox.run_root / "core-managed"
    restored: list[str] = []
    for relative in protected:
        source = protected_root / Path(relative)
        target = _agent_workspace(sandbox) / Path(relative)
        if not source.exists():
            continue
        if _path_digest(source) == _path_digest(target):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        _copy_path(source, target)
        restored.append(relative)
    return tuple(restored)


def update_run_manifest(path: Path, **updates: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    payload["updated_at"] = _now()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_agent_prompt(task: TaskPackage, *, reference_paths: tuple[str, ...]) -> str:
    direction_path = task.project_root / "workflow" / "studio" / "user_directions.md"
    direction = direction_path.read_text(encoding="utf-8", errors="ignore").strip() if direction_path.is_file() else ""
    return render_worker_program(task, user_direction=direction, reference_paths=reference_paths)


def sandbox_change_issues(sandbox: SandboxManifest) -> list[str]:
    baseline = json.loads(sandbox.baseline_path.read_text(encoding="utf-8"))
    current = _workspace_hashes(_agent_workspace(sandbox))
    unexpected = _unexpected_changes(baseline, current, sandbox.expected_outputs)
    return ["Agent runtime changed files outside expected_outputs: " + ", ".join(unexpected[:20])] if unexpected else []


def _unexpected_changes(
    baseline: dict[str, str],
    current: dict[str, str],
    expected_outputs: Iterable[str],
) -> list[str]:
    allowed = tuple(str(item).replace("\\", "/").rstrip("/") for item in expected_outputs)
    changed = sorted(set(baseline) | set(current))
    unexpected: list[str] = []
    for relative in changed:
        if baseline.get(relative) == current.get(relative):
            continue
        top = relative.split("/", 1)[0]
        if top in IGNORED_RUNTIME_PATHS:
            continue
        if any(relative == item or relative.startswith(item + "/") for item in allowed):
            continue
        unexpected.append(relative)
    return unexpected


def _control_workspace(sandbox: SandboxManifest) -> Path:
    return sandbox.control_workspace or sandbox.workspace


def _agent_workspace(sandbox: SandboxManifest) -> Path:
    return sandbox.agent_workspace or sandbox.workspace


def _workspace_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _path_digest(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = _workspace_hashes(path)
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode("utf-8")).hexdigest()


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _readable_diff(before: Path, after: Path, relative: str) -> str:
    if not after.is_file() or (before.exists() and not before.is_file()):
        return "目录内容发生变化；请查看文件清单。"
    if after.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".py"}:
        return "二进制或不可读文本文件；请核对文件大小与摘要。"
    before_lines = before.read_text(encoding="utf-8", errors="replace").splitlines() if before.is_file() else []
    after_lines = after.read_text(encoding="utf-8", errors="replace").splitlines()
    diff = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="正式项目/" + relative,
            tofile="候选写回/" + relative,
            lineterm="",
            n=3,
        )
    )
    if len(diff) > 180:
        diff = diff[:180] + ["... 差异过长，已在预览中截断 ..."]
    return "\n".join(diff)


def _copy_path(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError(f"symbolic links are not allowed in task sandboxes: {source}")
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).replace("\\", "/")
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _run_id(task_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", task_id).strip("-")[:48]
    return f"{stamp}-{safe}"


def _project_key(project: Path) -> str:
    digest = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", project.name).strip("-") or "project"
    return f"{safe[:36]}-{digest}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
