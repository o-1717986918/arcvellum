"""Subprocess bridge to the Literary Engineering CLI state machine."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
from typing import Iterable

from .config import core_repo_from_config


FORBIDDEN_COMMAND_TOKENS = (
    "--allow-unreviewed",
    "--allow-review-notes",
    "--include-blocked",
    "--allow-unapproved",
    "--allow-unresolved",
    "--allow-missing-composition",
    "--allow-unselected-composition",
    "--allow-recommended-branch",
    "--allow-missing-branch",
    "LEW_MAINTAINER_MODE",
)


@dataclass(frozen=True)
class CoreCommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    fields: dict[str, str]

    def require_success(self) -> "CoreCommandResult":
        if self.returncode:
            detail = self.stderr.strip() or self.stdout.strip() or f"exit code {self.returncode}"
            raise RuntimeError(f"Literary Engineering CLI failed: {detail}")
        return self


class CoreBridge:
    def __init__(self, config: dict[str, object]):
        self.config = config
        self.core_repo = core_repo_from_config(config)
        core = config.get("core", {}) if isinstance(config.get("core"), dict) else {}
        self.python = str(core.get("python") or "python")
        self.module = str(core.get("module") or "literary_engineering_workbench")

    def doctor(self) -> CoreCommandResult:
        return self.run(["--help"], timeout=30)

    def run(self, args: Iterable[str], *, timeout: int = 180) -> CoreCommandResult:
        command = [self.python, "-m", self.module, *[str(item) for item in args]]
        env = os.environ.copy()
        source_root = str(self.core_repo / "src")
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = source_root + (os.pathsep + current if current else "")
        env.pop("LEW_MAINTAINER_MODE", None)
        completed = subprocess.run(
            command,
            cwd=self.core_repo,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CoreCommandResult(
            args=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            fields=parse_cli_fields(completed.stdout),
        )

    def task_next(self, project: Path, route: str, *, scene: str = "") -> CoreCommandResult:
        args = ["task-next", str(project.resolve()), "--route", route]
        if scene:
            args.extend(["--scene", scene])
        return self.run(args).require_success()

    def task_open(self, project: Path, task_id: str) -> CoreCommandResult:
        return self.run(["task-open", str(project.resolve()), "--task-id", task_id]).require_success()

    def task_submit(self, project: Path, task_id: str, artifacts: Iterable[str], *, note: str = "") -> CoreCommandResult:
        args = ["task-submit", str(project.resolve()), "--task-id", task_id]
        for artifact in artifacts:
            args.extend(["--from", str(artifact)])
        if note:
            args.extend(["--note", note])
        return self.run(args).require_success()

    def task_complete(self, project: Path, task_id: str, *, handled_by: str) -> CoreCommandResult:
        return self.run(
            ["task-complete", str(project.resolve()), "--task-id", task_id, "--handled-by", handled_by]
        ).require_success()

    def route_audit(self, project: Path, route: str) -> CoreCommandResult:
        return self.run(["route-audit", str(project.resolve()), "--route", route]).require_success()

    def execute_task_command(self, command: str, project: Path, *, timeout: int = 600) -> CoreCommandResult:
        """Execute only trusted core-generated `python -m literary_engineering_workbench` commands."""

        if not command.strip():
            raise ValueError("task command is empty")
        if any(token in command for token in FORBIDDEN_COMMAND_TOKENS):
            raise ValueError("task command contains a formal-mode bypass token")
        if any(token in command for token in ("&&", "||", "|", ">", "< ", ";", "`")):
            raise ValueError("task command contains unsupported shell syntax")
        parts = [_unquote(item) for item in shlex.split(command, posix=False)]
        try:
            module_index = parts.index("-m")
        except ValueError as exc:
            raise ValueError("task command must use python -m literary_engineering_workbench") from exc
        if module_index + 1 >= len(parts) or parts[module_index + 1] != self.module:
            raise ValueError(f"task command module is not allowed: {parts[module_index + 1:]}")
        args = [_replace_project_placeholder(item, project.resolve()) for item in parts[module_index + 2 :]]
        if not args:
            raise ValueError("task command does not contain a core subcommand")
        return self.run(args, timeout=timeout).require_success()


def parse_cli_fields(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        normalized = key.strip()
        if normalized and all(char.isalnum() or char in "_-" for char in normalized):
            fields[normalized] = value.strip()
    return fields


def _replace_project_placeholder(value: str, project: Path) -> str:
    normalized = value.replace("<project>", str(project))
    return normalized.replace("/", os.sep) if normalized.startswith(str(project)) else normalized


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
