"""Validated formal-project and task-package path resolution for Worker flows."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.public.projects import is_authorized_demo_reference


def validate_project(value: Path) -> Path:
    project = value.expanduser().resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"work project not found: {project}")
    if not (project / "project.yaml").exists():
        raise ValueError(f"not a Literary Engineering work project: {project}")
    if is_authorized_demo_reference(project):
        raise ValueError(
            "授权演示母本为只读项目；请先在作品页复制为可编辑作品，再启动 Agent 任务。"
        )
    return project


def resolve_task_json_path(
    project: Path,
    task_id: str,
    reported_path: str = "",
) -> Path:
    """Resolve a formal task without trusting locale-sensitive CLI path text."""

    normalized_id = str(task_id or "").strip()
    if not normalized_id or any(char in normalized_id for char in ("/", "\\", ":")):
        raise ValueError(f"invalid task id: {task_id}")
    canonical = (
        project / "workflow" / "tasks" / f"{normalized_id}.task.json"
    ).resolve()
    if canonical.is_file():
        return canonical

    raw = str(reported_path or "").strip()
    if raw:
        candidate = Path(raw).resolve()
        if candidate.is_relative_to(project.resolve()) and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"formal task package not found for task: {normalized_id}")
