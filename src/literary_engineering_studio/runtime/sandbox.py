"""Per-task isolated workspaces and expected-output-only writeback."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable, Mapping

from literary_engineering_studio_engine.public.projects import engine_root
from ..contracts import TaskPackage
from .context_budget import TaskContextBudget
from .context_materialization import materialize_agent_context_contract
from .context_selection import select_agent_context
from .prepared_context_cache import PreparedContextCache
from .execution_boundaries import prepare_execution_boundaries
from .run_manifest import update_run_manifest
from .run_manifest_factory import build_run_manifest_payload
from .sandbox_contracts import SandboxManifest
from .sandbox_files import (
    agent_workspace as _agent_workspace,
    control_workspace as _control_workspace,
    copy_path as _copy_path,
    path_digest as _path_digest,
    remove_path as _remove_path,
    unique_paths as _unique,
    utc_now as _now,
    workspace_hashes as _workspace_hashes,
)
from .sandbox_writeback import (
    apply_expected_outputs,
    control_sandbox_view,
    inspect_expected_outputs as _inspect_expected_outputs,
    load_writeback_preview,
    rollback_expected_outputs,
    sync_agent_outputs_to_control,
)
from .task_snapshot import materialize_task_snapshot
from .writeback_contracts import WritebackPreview

IGNORED_RUNTIME_PATHS = {"AGENT_TASK.md", "_task", ".claude", ".codex", ".git"}

def stage_task(
    task: TaskPackage,
    runs_root: Path,
    *,
    runtime: str,
    run_id: str | None = None,
    materialize_agent_view: bool = True,
    context_budget: TaskContextBudget | None = None,
    prepared_context_cache: PreparedContextCache | None = None,
    execution_profile: dict[str, object] | None = None,
    prompt_program_config: Mapping[str, Any] | None = None,
) -> SandboxManifest:
    identifier = run_id or _run_id(task.task_id)
    run_root = runs_root.expanduser().resolve() / _project_key(task.project_root) / identifier
    if run_root.exists():
        raise FileExistsError(f"Studio run already exists: {run_root}")
    workspace = run_root / "workspace"
    control_workspace = run_root / "control-workspace"
    control_workspace.mkdir(parents=True, exist_ok=False)
    task_snapshot = materialize_task_snapshot(task, run_root)

    copied_sources: list[str] = []
    missing_sources: list[str] = []
    selection = select_agent_context(task)
    # Control receives exact CLI/preflight dependencies; the Agent receives a
    # separately bounded view.
    staged_sources = (*selection.reference_paths, *task.source_paths, *selection.source_paths)
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

    # Keep control runnable while excluding this descriptor from Agent writeback.
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
    payload = build_run_manifest_payload(
        task=task,
        run_id=identifier,
        runtime=runtime,
        created_at=_now(),
        workspace=workspace,
        control_workspace=control_workspace,
        prompt_path=prompt_path,
        copied_sources=copied_sources,
        missing_sources=missing_sources,
        reference_paths=selection.reference_paths,
        task_snapshot=task_snapshot,
        execution_fields=prepare_execution_boundaries(
            task, run_root, runtime=runtime
        ).run_manifest_fields(),
    )
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
    if materialize_agent_view:
        materialize_agent_workspace(
            task, sandbox, context_budget=context_budget,
            prepared_context_cache=prepared_context_cache,
            execution_profile=execution_profile,
            prompt_program_config=prompt_program_config,
        )
    else:
        workspace.mkdir(parents=True, exist_ok=False)
        baseline_path.write_text("{}\n", encoding="utf-8")
        update_run_manifest(manifest_path, agent_workspace_deferred=True, agent_baseline_file_count=0)
    return sandbox


def materialize_agent_workspace(
    task: TaskPackage, sandbox: SandboxManifest, *, context_budget: TaskContextBudget | None = None,
    prepared_context_cache: PreparedContextCache | None = None,
    execution_profile: dict[str, object] | None = None,
    prompt_program_config: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Build the bounded Agent view from the fully reproducible control view."""

    workspace = _agent_workspace(sandbox)
    _remove_path(workspace)
    workspace.mkdir(parents=True, exist_ok=False)
    selection = select_agent_context(task)
    visible_paths = list(selection.visible_paths)
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
    snapshot_root = sandbox.run_root / "task-snapshot"
    shutil.copy2(snapshot_root / "task.json", task_dir / "task.json")
    shutil.copy2(
        snapshot_root / "task.agent_tasks.md",
        task_dir / "task.agent_tasks.md",
    )
    (task_dir / "execution_contract.json").write_text(
        json.dumps(task.execution_contract.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    context = materialize_agent_context_contract(
        task,
        run_root=sandbox.run_root,
        run_id=sandbox.run_id,
        workspace=workspace,
        prompt_path=sandbox.prompt_path,
        task_dir=task_dir,
        selection=selection,
        copied_paths=copied,
        context_budget=context_budget,
        prepared_context_cache=prepared_context_cache,
        execution_profile=execution_profile,
        cache_identity_workspace=_control_workspace(sandbox),
        runtime_id=str((execution_profile or {}).get("runtime_id") or "host-agent"),
        prompt_program_config=prompt_program_config,
    )
    refresh_sandbox_baseline(sandbox)
    update_run_manifest(
        sandbox.manifest_path,
        agent_visible_paths=visible_paths,
        agent_copied_sources=copied,
        agent_missing_sources=missing,
        agent_prompt_source_paths=list(context.source_paths),
        agent_prompt_reference_paths=list(context.reference_paths),
        **context.run_manifest_fields(sandbox.run_root),
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


def inspect_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> WritebackPreview:
    return _inspect_expected_outputs(
        task,
        sandbox,
        change_issues=sandbox_change_issues,
    )


def import_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    preview = inspect_expected_outputs(task, sandbox)
    return apply_expected_outputs(task, sandbox, preview)


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


def sandbox_change_issues(sandbox: SandboxManifest) -> list[str]:
    baseline = json.loads(sandbox.baseline_path.read_text(encoding="utf-8"))
    current = _workspace_hashes(_agent_workspace(sandbox))
    unexpected = _unexpected_changes(baseline, current, sandbox.expected_outputs)
    return ["Agent runtime changed files outside expected_outputs: " + ", ".join(unexpected[:20])] if unexpected else []


def changed_agent_outputs(sandbox: SandboxManifest, *, include_completion_receipts: bool = False) -> tuple[str, ...]:
    """Return declared outputs that changed after the Agent workspace was staged.

    Recovery may only reuse a timed-out sandbox when the Agent actually wrote a
    fresh, substantive output.  Completion receipts are Worker-owned and are
    therefore excluded by default: a receipt alone must never make stale prose
    or a stale review recoverable.
    """

    baseline = json.loads(sandbox.baseline_path.read_text(encoding="utf-8"))
    current = _workspace_hashes(_agent_workspace(sandbox))
    changed: list[str] = []
    for relative in sandbox.expected_outputs:
        normalized = str(relative).replace("\\", "/")
        if not include_completion_receipts and normalized.endswith(".agent_completion.json"):
            continue
        if baseline.get(normalized) != current.get(normalized):
            changed.append(normalized)
    return tuple(changed)


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


def _run_id(task_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", task_id).strip("-")[:48]
    return f"{stamp}-{safe}"


def _project_key(project: Path) -> str:
    digest = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", project.name).strip("-") or "project"
    return f"{safe[:36]}-{digest}"
