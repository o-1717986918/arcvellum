"""Per-task isolated workspaces and expected-output-only writeback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable

from literary_engineering_studio_engine.resources import engine_root

from .contracts import TaskPackage
from .task_program import compact_task_references, render_worker_program, write_task_context


MANIFEST_SCHEMA = "literary-engineering-studio/task-sandbox/v0.1"
IGNORED_RUNTIME_PATHS = {"AGENT_TASK.md", "_task", ".claude", ".codex", ".git"}


@dataclass(frozen=True)
class SandboxManifest:
    run_id: str
    run_root: Path
    workspace: Path
    prompt_path: Path
    manifest_path: Path
    baseline_path: Path
    expected_outputs: tuple[str, ...]


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
    task_dir = workspace / "_task"
    task_dir.mkdir(parents=True, exist_ok=False)

    copied_sources: list[str] = []
    missing_sources: list[str] = []
    reference_paths = compact_task_references(task)
    for relative in _unique([*reference_paths, *task.source_paths]):
        source = task.resolve_project_path(relative)
        if not source.exists():
            embedded = engine_root() / Path(relative)
            if embedded.exists():
                source = embedded
        if not source.exists():
            missing_sources.append(relative)
            continue
        _copy_path(source, workspace / Path(relative))
        copied_sources.append(relative)

    for relative in task.expected_outputs:
        source = task.resolve_project_path(relative)
        destination = workspace / Path(relative)
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
        _copy_path(project_descriptor, workspace / "project.yaml")
        if "project.yaml" not in copied_sources:
            copied_sources.append("project.yaml")

    direction_digest = task.project_root / "workflow" / "studio" / "user_directions.md"
    if direction_digest.is_file():
        relative = "workflow/studio/user_directions.md"
        _copy_path(direction_digest, workspace / Path(relative))
        copied_sources.append(relative)

    shutil.copy2(task.task_json_path, task_dir / "task.json")
    shutil.copy2(task.task_markdown_path, task_dir / "task.agent_tasks.md")
    (task_dir / "execution_contract.json").write_text(
        json.dumps(task.execution_contract.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    prompt_path = workspace / "AGENT_TASK.md"
    prompt_path.write_text(_render_agent_prompt(task, reference_paths=reference_paths), encoding="utf-8")
    write_task_context(task, workspace / "TASK_CONTEXT.json", reference_paths=reference_paths)
    baseline = _workspace_hashes(workspace)
    baseline_path = run_root / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    return SandboxManifest(
        run_id=identifier,
        run_root=run_root,
        workspace=workspace,
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        baseline_path=baseline_path,
        expected_outputs=task.expected_outputs,
    )


def inspect_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> WritebackPreview:
    baseline = json.loads(sandbox.baseline_path.read_text(encoding="utf-8"))
    current = _workspace_hashes(sandbox.workspace)
    unexpected = _unexpected_changes(baseline, current, sandbox.expected_outputs)
    if unexpected:
        raise ValueError(
            "Agent runtime changed files outside expected_outputs: " + ", ".join(unexpected[:20])
        )

    missing: list[str] = []
    for relative in sandbox.expected_outputs:
        if not (sandbox.workspace / Path(relative)).exists():
            missing.append(relative)
    if missing:
        raise FileNotFoundError("Agent runtime did not create expected outputs: " + ", ".join(missing))

    contracts = {item.path: item for item in task.execution_contract.outputs}
    changes: list[dict[str, object]] = []
    for relative in sandbox.expected_outputs:
        source = sandbox.workspace / Path(relative)
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
    imported: list[str] = []
    for relative in sandbox.expected_outputs:
        source = sandbox.workspace / Path(relative)
        target = task.resolve_project_path(relative)
        if target.exists():
            _copy_path(target, backup_root / Path(relative))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        _copy_path(source, target)
        imported.append(relative)
    update_run_manifest(sandbox.manifest_path, status="outputs_imported", imported_outputs=imported)
    return tuple(imported)


def import_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
    preview = inspect_expected_outputs(task, sandbox)
    return apply_expected_outputs(task, sandbox, preview)


def rollback_expected_outputs(task: TaskPackage, sandbox: SandboxManifest, imported: Iterable[str]) -> None:
    backup_root = sandbox.run_root / "backups"
    for relative in imported:
        target = task.resolve_project_path(relative)
        backup = backup_root / Path(relative)
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if backup.exists():
            _copy_path(backup, target)
    update_run_manifest(sandbox.manifest_path, status="writeback_rolled_back")


def sandbox_from_run(run_root: Path) -> SandboxManifest:
    root = run_root.expanduser().resolve()
    manifest_path = root / "run.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    workspace = Path(str(payload["workspace"])).resolve()
    return SandboxManifest(
        run_id=str(payload["run_id"]),
        run_root=root,
        workspace=workspace,
        prompt_path=Path(str(payload["prompt"])).resolve(),
        manifest_path=manifest_path,
        baseline_path=root / "baseline.json",
        expected_outputs=tuple(str(item) for item in payload.get("expected_outputs") or []),
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
        source = sandbox.workspace / Path(relative)
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
        target = sandbox.workspace / Path(relative)
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
    current = _workspace_hashes(sandbox.workspace)
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
