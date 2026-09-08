"""CLI adapter for the lean scene-transaction application service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    SceneExecutionMode,
    SceneTransactionStatus,
)

from ..infrastructure.composition import resolve_application_container
from ..infrastructure.lean_scene_runtime import build_lean_scene_runtime
from ..persistence.scene_transactions import SceneTransactionRepository


COMMAND_PREFIX = "scene-transaction-"


def register_scene_transaction_commands(subparsers: Any) -> None:
    status = subparsers.add_parser(
        "scene-transaction-status",
        help="Inspect lean scene transactions without changing project state.",
    )
    status.add_argument("project")
    status.add_argument("--scene", default="")
    status.add_argument("--transaction-id", default="")
    status.add_argument("--limit", type=int, default=20)

    prepare = subparsers.add_parser(
        "scene-transaction-prepare",
        help="Prepare one recoverable lean scene transaction.",
    )
    prepare.add_argument("project")
    prepare.add_argument("scene")
    prepare.add_argument(
        "--mode",
        choices=[item.value for item in SceneExecutionMode],
        default=SceneExecutionMode.STANDARD.value,
    )

    run = subparsers.add_parser(
        "scene-transaction-run",
        help="Run an existing lean scene transaction through production state logic.",
    )
    run.add_argument("project")
    run.add_argument("transaction_id")
    run.add_argument("--max-steps", type=int, default=12)
    run.add_argument("--steward-approved", action="store_true")

    resume = subparsers.add_parser(
        "scene-transaction-resume",
        help="Resume one blocked or interrupted lean scene transaction.",
    )
    resume.add_argument("project")
    resume.add_argument("transaction_id")


def is_scene_transaction_command(command: str) -> bool:
    return command.startswith(COMMAND_PREFIX)


def run_scene_transaction_command(args: argparse.Namespace, config: dict[str, object]) -> int:
    project = _project_root(args.project)
    container = resolve_application_container(config, None)
    repository = SceneTransactionRepository(container.ports.persistence.unit_of_work)
    try:
        handlers: dict[str, Callable[..., int]] = {
            "scene-transaction-status": _status,
            "scene-transaction-prepare": _prepare,
            "scene-transaction-run": _run,
            "scene-transaction-resume": _resume,
        }
        return handlers[args.command](args, config, project, repository)
    finally:
        container.shutdown()


def _status(args: Any, _config: Any, project: Path, repository: Any) -> int:
    if args.transaction_id:
        items = [repository.load(args.transaction_id)]
    elif args.scene:
        latest = repository.latest_for_scene(str(project), args.scene)
        items = [latest] if latest is not None else []
    else:
        items = repository.list_for_project(str(project), limit=args.limit)
    _print_json(
        {
            "status": "ready",
            "project_root": str(project),
            "items": [item.to_dict() for item in items],
        }
    )
    return 0


def _prepare(args: Any, config: dict[str, object], project: Path, repository: Any) -> int:
    bundle = _runtime(config, project, repository)
    existing = repository.latest_for_scene(str(project), args.scene)
    reused = existing is not None and existing.status is not SceneTransactionStatus.CANCELLED
    transaction = existing if reused else bundle.service.prepare(
        project,
        args.scene,
        mode=SceneExecutionMode(args.mode),
    )
    _print_json({"status": "prepared", "reused": reused, "transaction": transaction.to_dict()})
    return 0


def _resume(args: Any, config: dict[str, object], project: Path, repository: Any) -> int:
    bundle = _runtime(config, project, repository)
    transaction = _require_project(repository.load(args.transaction_id), project)
    resumed = bundle.service.resume(transaction.transaction_id)
    _print_json({"status": "resumed", "transaction": resumed.to_dict()})
    return 0


def _run(args: Any, config: dict[str, object], project: Path, repository: Any) -> int:
    bundle = _runtime(config, project, repository)
    transaction = _require_project(repository.load(args.transaction_id), project)
    steps: list[dict[str, object]] = []
    for _ in range(_remaining_steps(transaction, args.max_steps)):
        step = bundle.coordinator.advance_transaction(
            transaction.transaction_id,
            steward_approved=bool(args.steward_approved),
        )
        steps.append(step.__dict__)
        transaction = repository.load(transaction.transaction_id)
        if step.committed or step.blocked or step.waiting_human:
            break
    _print_json({"status": transaction.status.value, "steps": steps, "transaction": transaction.to_dict()})
    return 0 if transaction.status is not SceneTransactionStatus.BLOCKED else 1


def _runtime(config: dict[str, object], project: Path, repository: Any) -> Any:
    return build_lean_scene_runtime(
        config,
        project_root=project,
        data_root=_application_data_root(config),
        repository=repository,
    )


def _remaining_steps(transaction: Any, maximum: int) -> range:
    if transaction.status is SceneTransactionStatus.COMMITTED:
        return range(0)
    return range(max(1, min(32, int(maximum))))


def _project_root(value: str) -> Path:
    project = Path(value).expanduser().resolve()
    if not (project / "project.yaml").is_file():
        raise FileNotFoundError(f"Literary project not found: {project}")
    return project


def _application_data_root(config: dict[str, object]) -> Path:
    application = config.get("application")
    values = application if isinstance(application, dict) else {}
    return Path(str(values.get("data_root") or ".")).expanduser().resolve()


def _require_project(transaction: Any, project: Path) -> Any:
    if Path(transaction.project_root).resolve() != project:
        raise ValueError("scene transaction belongs to another project")
    return transaction


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


__all__ = [
    "is_scene_transaction_command",
    "register_scene_transaction_commands",
    "run_scene_transaction_command",
]
