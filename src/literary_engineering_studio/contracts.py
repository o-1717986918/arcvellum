"""Consumer-side validation for Literary Engineering task packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any


TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
HUMAN_GATE_TOKENS = (
    "human-choice",
    "human_approval",
    "approval",
    "canon-apply",
    "state-apply",
    "release-approval",
    "publish-approval",
)


@dataclass(frozen=True)
class TaskPackage:
    project_root: Path
    task_json_path: Path
    task_markdown_path: Path
    payload: dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.payload["task_id"])

    @property
    def route(self) -> str:
        return str(self.payload.get("route") or "")

    @property
    def current_state(self) -> str:
        return str(self.payload.get("current_state") or "")

    @property
    def command(self) -> str:
        return str(self.payload.get("command") or "").strip()

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("source_paths") or [])

    @property
    def required_reading(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("required_reading") or [])

    @property
    def expected_outputs(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.payload.get("expected_outputs") or [])

    @property
    def human_gate_reasons(self) -> tuple[str, ...]:
        haystack = " ".join(
            [
                self.current_state,
                str(self.payload.get("task_type") or ""),
                str(self.payload.get("prompt_asset_id") or ""),
            ]
        ).lower()
        return tuple(token for token in HUMAN_GATE_TOKENS if token in haystack)

    def resolve_project_path(self, relative: str) -> Path:
        normalized = normalize_relative_path(relative)
        target = (self.project_root / Path(*normalized.parts)).resolve()
        if not target.is_relative_to(self.project_root):
            raise ValueError(f"task path escapes project root: {relative}")
        return target


def load_task_package(project_root: Path, task_json_path: Path) -> TaskPackage:
    root = project_root.resolve()
    path = task_json_path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"task JSON must be inside the work project: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid task JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"task JSON must be an object: {path}")
    _validate_task_payload(payload)
    markdown_rel = str(payload.get("task_markdown") or "")
    if not markdown_rel:
        markdown_rel = f"workflow/tasks/{payload['task_id']}.agent_tasks.md"
    markdown_path = (root / Path(*normalize_relative_path(markdown_rel).parts)).resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(f"task Markdown not found: {markdown_path}")
    return TaskPackage(root, path, markdown_path, payload)


def normalize_relative_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("task path must not be empty")
    path = PurePosixPath(text)
    if path.is_absolute() or ":" in path.parts[0] or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"task path must be a normalized project-relative path: {value}")
    return path


def _validate_task_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema") != TASK_SCHEMA:
        raise ValueError(f"unsupported task schema: {payload.get('schema')}")
    for field in ("task_id", "route", "current_state", "task_type"):
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"task package missing {field}")
    for field in ("required_reading", "source_paths", "expected_outputs"):
        values = payload.get(field)
        if not isinstance(values, list):
            raise ValueError(f"task package field must be a list: {field}")
        for value in values:
            normalize_relative_path(str(value))
    for field in ("validation_gates", "forbidden_shortcuts"):
        if not isinstance(payload.get(field), list):
            raise ValueError(f"task package field must be a list: {field}")

