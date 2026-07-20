"""Per-task isolated workspaces and expected-output-only writeback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable

from literary_engineering_studio_engine.resources import engine_root

from .contracts import TaskPackage


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
    for relative in _unique([*task.required_reading, *task.source_paths]):
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

    direction_digest = task.project_root / "workflow" / "studio" / "user_directions.md"
    if direction_digest.is_file():
        relative = "workflow/studio/user_directions.md"
        _copy_path(direction_digest, workspace / Path(relative))
        copied_sources.append(relative)

    shutil.copy2(task.task_json_path, task_dir / "task.json")
    shutil.copy2(task.task_markdown_path, task_dir / "task.agent_tasks.md")
    prompt_path = workspace / "AGENT_TASK.md"
    prompt_path.write_text(_render_agent_prompt(task), encoding="utf-8")
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
        "route": task.route,
        "current_state": task.current_state,
        "workspace": str(workspace),
        "prompt": str(prompt_path),
        "copied_sources": copied_sources,
        "missing_sources": missing_sources,
        "expected_outputs": list(task.expected_outputs),
        "human_gate_reasons": list(task.human_gate_reasons),
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


def import_expected_outputs(task: TaskPackage, sandbox: SandboxManifest) -> tuple[str, ...]:
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


def update_run_manifest(path: Path, **updates: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    payload["updated_at"] = _now()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_agent_prompt(task: TaskPackage) -> str:
    task_text = task.task_markdown_path.read_text(encoding="utf-8")
    outputs = "\n".join(f"- {item}" for item in task.expected_outputs) or "- 无固定文件输出"
    direction_path = task.project_root / "workflow" / "studio" / "user_directions.md"
    direction = direction_path.read_text(encoding="utf-8", errors="ignore").strip() if direction_path.is_file() else ""
    direction_block = f"\n## Current User Direction\n\n{direction}\n" if direction else ""
    return f"""# Studio Agent Execution Contract

你是本次任务的主 Agent。当前目录是隔离任务工作区，不是正式项目根目录。

硬约束：

1. 只读取当前工作区中已提供的资料。
2. 只创建或修改下列 expected outputs；不要修改 source artifacts。
3. 不运行 task-submit、task-complete、route-audit，也不伪造完成标记；Studio Worker 会在写回后执行正式 CLI 验收。
4. 不使用任何 debug waiver、绕过标志或 maintainer mode。
5. 正文、修订和最终文学文本必须由当前主 Agent 亲自完成，不委派给 subagent。
6. 完成文件后即可结束；聊天回复不是正式产物。

## Allowed Outputs

{outputs}
{direction_block}

## Core Task Package

{task_text}
"""


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
