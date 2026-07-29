"""Immutable run-scoped snapshots of machine-bound formal task packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage, load_task_package_snapshot


SNAPSHOT_SCHEMA = "literary-engineering-studio/task-snapshot/v1"


@dataclass(frozen=True)
class TaskSnapshot:
    json_path: Path
    markdown_path: Path
    json_sha256: str
    markdown_sha256: str
    digest: str

    def manifest_projection(self, run_root: Path) -> dict[str, str]:
        return {
            "schema": SNAPSHOT_SCHEMA,
            "json_path": self.json_path.relative_to(run_root).as_posix(),
            "markdown_path": self.markdown_path.relative_to(run_root).as_posix(),
            "json_sha256": self.json_sha256,
            "markdown_sha256": self.markdown_sha256,
            "digest": self.digest,
        }


def materialize_task_snapshot(task: TaskPackage, run_root: Path) -> TaskSnapshot:
    root = run_root.expanduser().resolve()
    target = root / "task-snapshot"
    target.mkdir(parents=True, exist_ok=False)
    json_path = target / "task.json"
    markdown_path = target / "task.agent_tasks.md"
    json_path.write_text(
        json.dumps(task.payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_bytes(task.task_markdown_path.read_bytes())
    return _snapshot(json_path, markdown_path)


def load_run_task_snapshot(
    run_root: Path,
    *,
    project_root: Path,
    manifest: dict[str, Any] | None = None,
) -> TaskPackage:
    root = run_root.expanduser().resolve()
    run = manifest or json.loads((root / "run.json").read_text(encoding="utf-8"))
    projection = run.get("task_snapshot")
    if not isinstance(projection, dict) or projection.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("run does not contain an immutable task snapshot")
    json_path = _snapshot_path(root, projection.get("json_path"))
    markdown_path = _snapshot_path(root, projection.get("markdown_path"))
    observed = _snapshot(json_path, markdown_path)
    expected = {
        key: str(projection.get(key) or "")
        for key in ("json_sha256", "markdown_sha256", "digest")
    }
    if (
        observed.json_sha256 != expected["json_sha256"]
        or observed.markdown_sha256 != expected["markdown_sha256"]
        or observed.digest != expected["digest"]
    ):
        raise RuntimeError("run task snapshot digest mismatch")
    task = load_task_package_snapshot(project_root, json_path, markdown_path)
    if task.task_id != str(run.get("task_id") or ""):
        raise RuntimeError("run task snapshot identity mismatch")
    plan = run.get("creative_plan")
    if isinstance(plan, dict) and _plan_identity(task.payload) != _plan_identity(plan):
        raise RuntimeError("run task snapshot creative plan identity mismatch")
    return task


def _snapshot(json_path: Path, markdown_path: Path) -> TaskSnapshot:
    if not json_path.is_file() or not markdown_path.is_file():
        raise FileNotFoundError("run task snapshot is incomplete")
    json_digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    markdown_digest = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
    body = json.dumps(
        {
            "json_sha256": json_digest,
            "markdown_sha256": markdown_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return TaskSnapshot(
        json_path=json_path,
        markdown_path=markdown_path,
        json_sha256=json_digest,
        markdown_sha256=markdown_digest,
        digest=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def _snapshot_path(run_root: Path, value: object) -> Path:
    relative = Path(str(value or "").replace("\\", "/"))
    target = (run_root / relative).resolve()
    if not relative.parts or relative.is_absolute() or not target.is_relative_to(run_root):
        raise ValueError("run task snapshot path is invalid")
    return target


def _plan_identity(payload: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(payload.get("creative_plan_id") or payload.get("plan_id") or ""),
        int(payload.get("creative_plan_revision") or payload.get("revision") or 0),
        str(payload.get("creative_plan_node_id") or payload.get("node_id") or ""),
    )
