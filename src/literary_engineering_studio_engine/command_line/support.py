"""Small CLI-only formatting and path helpers."""

from __future__ import annotations

from pathlib import Path

from ..agent_tasks import default_agent_completion_path


def cli_path(root: Path, value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    return path if path.is_absolute() else root / path


def print_agent_task_notice(task_path: Path, *, project: Path | None = None) -> None:
    marker = default_agent_completion_path(task_path)
    print(f"agent_tasks_pending: {task_path}")
    print(f"completion_receipt: {marker}")
    if project is not None:
        print(f"next_check: python -m literary_engineering_studio_engine agent-task-status \"{project}\"")
    print("next_action: read the .agent_tasks.md sidecar and write the declared Agent-authored artifacts. Studio Worker creates the lifecycle receipt after deterministic preflight succeeds.")


def print_human_decision_notice(task_path: Path, *, project: Path | None = None) -> None:
    print(f"human_decision_required: {task_path}")
    if project is not None:
        print(f"decision_project: {project}")
    print("next_action: review the offered options in Studio and record one deliberate decision. Do not create Agent artifacts or completion markers for this task.")


def read_prompt_arg(project: Path, file_arg: str, text_arg: str, label: str) -> str:
    if text_arg:
        return text_arg
    if not file_arg:
        raise ValueError(f"{label} prompt requires --{label} or --{label}-text")
    path = Path(file_arg)
    if not path.is_absolute():
        path = project / path
    if not path.exists():
        raise ValueError(f"{label} prompt file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def render_formal_help(project: str, route: str) -> str:
    project_arg = f'"{project}"' if project else '"<project>"'
    route_arg = route or "scene-development"
    return f"""# LEW Formal Host Loop

You are operating a work project through the CLI state machine, not freehand editing the repository.

## Start Here

1. `python -m literary_engineering_studio_engine workflow-dashboard {project_arg}`
2. `python -m literary_engineering_studio_engine task-next {project_arg} --route {route_arg}`
3. `python -m literary_engineering_studio_engine task-open {project_arg} --task-id <task_id>`
4. Read only the task package, prompt asset, and listed source_paths unless the task permits more.
5. Write only expected_outputs.
6. `python -m literary_engineering_studio_engine task-submit {project_arg} --task-id <task_id> --artifact <path>`
7. `python -m literary_engineering_studio_engine task-complete {project_arg} --task-id <task_id>`
8. `python -m literary_engineering_studio_engine route-audit {project_arg} --route {route_arg}`

## Discipline

- Do not handwrite CLI-generated flow artifacts as formal work.
- Do not skip `.agent_tasks.md` sidecars or completion markers.
- Do not use debug/bypass flags during formal Skill-host work.
- Do not set `LEW_MAINTAINER_MODE=1` unless you are explicitly maintaining the repository or running regression tests.
- Do not let subagents write body prose.
- Do not promote, export, release, state-apply, or canon-apply without a clean route audit and the required approvals.
- Use `canon-backlog` before export/release when canon patches may exist; `canon-evolve` only creates candidates.

## Command Surface

Use `workflow-dashboard`, `workflow-state`, `task-next`, `task-open`, `task-submit`, `task-complete`, `workflow-advance`, `agent-task-status`, `canon-backlog`, and `route-audit` as the main operating surface. Other commands are route internals unless a current task package explicitly instructs you to run them. Use `help-all` only for maintainer/debug discovery.
"""
