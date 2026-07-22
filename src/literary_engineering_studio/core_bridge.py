"""Subprocess bridge to the Literary Engineering CLI state machine."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import sys
from typing import Iterable

from .config import repository_root
from .core_read_models import ENGINE_ACCESS_LOCK
from .subprocess_utils import run_hidden


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

FORBIDDEN_ENGINE_SUBCOMMANDS = {
    "agent-run",
    "agent-repair",
    "config-init",
    "config-set-profile",
    "config-show",
    "dify-dsl",
    "director-chat",
    "run-langgraph",
    "run-workflow",
    "serve-api",
}


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
        self.working_dir = repository_root()
        engine = config.get("engine", {}) if isinstance(config.get("engine"), dict) else {}
        self.module = str(engine.get("module") or "literary_engineering_studio_engine")
        configured_python = str(engine.get("python") or "python")
        self.python = _source_checkout_python(self.working_dir, self.module, configured_python)

    def doctor(self) -> CoreCommandResult:
        return self.run(["--help"], timeout=30)

    def run(self, args: Iterable[str], *, timeout: int = 180) -> CoreCommandResult:
        engine_args = [str(item) for item in args]
        _assert_studio_engine_args(engine_args)
        command = [self.python, "-m", self.module, *engine_args]
        env = os.environ.copy()
        env.pop("LEW_MAINTAINER_MODE", None)
        with ENGINE_ACCESS_LOCK:
            completed = run_hidden(
                command,
                cwd=self.working_dir,
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
        """Execute only trusted core-generated `python -m literary_engineering_studio_engine` commands."""

        if not command.strip():
            raise ValueError("task command is empty")
        parameters = task_command_parameters(command)
        if parameters:
            raise ValueError("task command is a template and requires: " + ", ".join(parameters))
        if any(token in command for token in FORBIDDEN_COMMAND_TOKENS):
            raise ValueError("task command contains a formal-mode bypass token")
        # Commands run as an argument vector, never through a shell.  Keep the
        # reject list for real shell-control syntax, but only after unresolved
        # template fields have been surfaced as a human gate above.
        shell_check = command.replace("<project>", "")
        if any(token in shell_check for token in ("&&", "||", "|", ">", "< ", ";", "`")):
            raise ValueError("task command contains unsupported shell syntax")
        parts = [_unquote(item) for item in shlex.split(command, posix=False)]
        try:
            module_index = parts.index("-m")
        except ValueError as exc:
            raise ValueError("task command must use python -m literary_engineering_studio_engine") from exc
        if module_index + 1 >= len(parts) or parts[module_index + 1] != self.module:
            raise ValueError(f"task command module is not allowed: {parts[module_index + 1:]}")
        args = [_replace_project_placeholder(item, project.resolve()) for item in parts[module_index + 2 :]]
        if not args:
            raise ValueError("task command does not contain a core subcommand")
        return self.run(args, timeout=timeout).require_success()


def task_command_parameters(command: str) -> tuple[str, ...]:
    """Return unresolved placeholders from a core command template.

    ``<project>`` is the only placeholder Studio is allowed to materialize on
    its own. Asset intake templates intentionally contain choices such as
    ``<type>`` or ``<user brief>``; attempting to execute those strings makes
    the task look like a shell failure instead of an honest decision gate.
    """

    normalized = str(command or "").replace("<project>", "")
    optional_values = [item.strip() for item in re.findall(r"\[([^\]]+)\]", normalized)]
    required_source = re.sub(r"\[[^\]]+\]", "", normalized)
    values = [item.strip() for item in re.findall(r"<([^>]+)>", required_source)]
    values.extend(optional_values)
    return tuple(dict.fromkeys(item for item in values if item))


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


def _source_checkout_python(working_dir: Path, module: str, configured_python: str) -> str:
    """Avoid executing a stale installed sidecar while the Studio runs from source."""

    module_dir = working_dir / "src" / module.replace(".", os.sep)
    if (working_dir / "pyproject.toml").is_file() and module_dir.is_dir() and configured_python.lower().endswith(".exe"):
        return sys.executable
    return configured_python


def _assert_studio_engine_args(args: list[str]) -> None:
    if not args:
        raise ValueError("embedded engine command is empty")
    subcommand = next((item for item in args if item and not item.startswith("-")), "")
    if subcommand in FORBIDDEN_ENGINE_SUBCOMMANDS:
        raise ValueError(f"embedded model/provider command is not available in Studio: {subcommand}")
    if any(item.startswith("--api-key") for item in args):
        raise ValueError("model credentials are not accepted by the Studio engine bridge")
    if "--provider" in args:
        index = args.index("--provider")
        provider = args[index + 1] if index + 1 < len(args) else ""
        if provider != "platform-agent":
            raise ValueError("Studio only permits platform-agent task generation; direct model providers are disabled")
