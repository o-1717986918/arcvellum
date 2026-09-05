"""Subprocess bridge to the Literary Engineering CLI state machine."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Iterable

from literary_engineering_studio_engine.public.tasking import (
    EngineOperation,
    operation_from_legacy_command,
    operation_parameters,
    resolve_operation_argv,
)

from ..application.config import repository_root
from ..projections.core_read_models import ENGINE_ACCESS_LOCK
from .subprocess_utils import run_hidden


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
        # Frozen Windows sidecars inherit the machine console code page unless
        # Python's UTF-8 mode is explicit. CLI fields carry project paths and
        # titles, so legacy decoding can otherwise corrupt a valid Chinese
        # project path before Studio validates the task package.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        _prefer_source_checkout(env, self.working_dir, self.module)
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

    def task_next(
        self,
        project: Path,
        route: str,
        *,
        scene: str = "",
        force: bool = False,
    ) -> CoreCommandResult:
        args = ["task-next", str(project.resolve()), "--route", route]
        if scene:
            args.extend(["--scene", scene])
        if force:
            args.append("--force")
        return self.run(args).require_success()

    def task_open(self, project: Path, task_id: str) -> CoreCommandResult:
        return self.run(["task-open", str(project.resolve()), "--task-id", task_id]).require_success()

    def task_contract_replay(
        self,
        project: Path,
        task_id: str,
    ) -> CoreCommandResult:
        return self.run(
            [
                "task-contract-replay",
                str(project.resolve()),
                "--task-id",
                task_id,
            ]
        ).require_success()

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

    def task_revert_submission(self, project: Path, task_id: str, *, reason: str) -> CoreCommandResult:
        return self.run(
            ["task-revert-submission", str(project.resolve()), "--task-id", task_id, "--reason", reason]
        ).require_success()

    def route_audit(self, project: Path, route: str) -> CoreCommandResult:
        return self.run(["route-audit", str(project.resolve()), "--route", route]).require_success()

    def execute_task_command(self, command: str, project: Path, *, timeout: int = 600) -> CoreCommandResult:
        """Upgrade a persisted v1 command and execute its registered operation."""

        if not command.strip():
            raise ValueError("task command is empty")
        operation = operation_from_legacy_command(command)
        if operation is None:
            raise ValueError("task command must use python -m literary_engineering_studio_engine")
        return self.execute_task_operation(operation, project, timeout=timeout)

    def execute_task_operation(
        self,
        operation: EngineOperation,
        project: Path,
        *,
        timeout: int = 600,
    ) -> CoreCommandResult:
        args = resolve_operation_argv(operation, project)
        return self.run(args, timeout=timeout).require_success()


def task_command_parameters(command: str) -> tuple[str, ...]:
    """Return unresolved placeholders from a core command template.

    ``<project>`` is the only placeholder Studio is allowed to materialize on
    its own. Asset intake templates intentionally contain choices such as
    ``<type>`` or ``<user brief>``; attempting to execute those strings makes
    the task look like a shell failure instead of an honest decision gate.
    """

    operation = operation_from_legacy_command(command)
    if operation is None:
        return ()
    return operation_parameters(operation)


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


def _source_checkout_python(working_dir: Path, module: str, configured_python: str) -> str:
    """Use the active runtime when a persisted executable path can be stale."""

    if getattr(sys, "frozen", False):
        return sys.executable
    module_dir = working_dir / "src" / module.replace(".", os.sep)
    if (working_dir / "pyproject.toml").is_file() and module_dir.is_dir() and configured_python.lower().endswith(".exe"):
        return sys.executable
    return configured_python


def _prefer_source_checkout(env: dict[str, str], working_dir: Path, module: str) -> None:
    """Keep the CLI subprocess on the same Engine revision as Studio."""

    if getattr(sys, "frozen", False):
        return
    source_root = working_dir / "src"
    module_dir = source_root / module.replace(".", os.sep)
    if not (working_dir / "pyproject.toml").is_file() or not module_dir.is_dir():
        return
    existing = str(env.get("PYTHONPATH") or "")
    values = [str(source_root), *[item for item in existing.split(os.pathsep) if item]]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(values))


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
