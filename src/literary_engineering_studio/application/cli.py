"""Studio command line interface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .. import __version__
from .config import default_config_path, load_config, save_config
from ..runtime.engine_bridge import CoreBridge
from ..integrations.model_connections import model_connection_status
from .project_manager import create_project, list_projects, record_direction, register_project
from ..automation.prompt_evaluation import evaluate_prompt_assets, write_prompt_evaluation
from ..integrations.runner_probe import probe_agent_runner
from ..runtimes import agent_runner_status
from ..runtime.sidecar_protocol import (
    bound_port as _bound_port,
    is_loopback_host as _is_loopback_host,
    serve_with_ready_file as _serve_with_ready_file,
    validate_serve_binding as _validate_serve_binding,
    write_ready_file as _write_ready_file,
)
from ..runtime.worker import AgentWorker
from ..runtime.runtime_selection import DEFAULT_CREATIVE_RUNTIME
from ..infrastructure.composition import resolve_application_container
from ..infrastructure.lean_scene_runtime import build_lean_scene_runtime
from ..persistence.scene_transactions import SceneTransactionRepository
from literary_engineering_studio_engine.literary.scene.transaction import (
    SceneExecutionMode,
    SceneTransactionStatus,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="les",
        description="Literary Engineering Studio: standalone project client, embedded workflow engine, and controlled Agent Worker.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("config-init", help="Write a credential-free Studio configuration.")
    sub.add_parser("doctor", help="Check the embedded engine, Agent Runners, and Model Connections.")
    runner_probe = sub.add_parser("runner-probe", help="Run an isolated real inference probe for an Agent Runner.")
    runner_probe.add_argument("--runner", choices=["pi-worker", "claude-code", "codex-cli"], required=True)
    runner_probe.add_argument("--model", default="")
    runner_probe.add_argument("--timeout", type=int, default=90)
    prompt_eval = sub.add_parser("prompt-eval", help="Run deterministic and optional live semantic prompt regressions.")
    prompt_eval.add_argument("--output", default="")
    prompt_eval.add_argument("--live", action="store_true")
    prompt_eval.add_argument("--runner", choices=["pi-worker", "claude-code", "codex-cli"], default="pi-worker")
    prompt_eval.add_argument("--model", default="")
    prompt_eval.add_argument("--timeout", type=int, default=240)

    project_list = sub.add_parser("project-list", help="List Studio projects and the current project.")
    project_list.set_defaults(project_command="list")
    project_open = sub.add_parser("project-open", help="Register and select an existing literary project.")
    project_open.add_argument("project")
    project_create = sub.add_parser("project-create", help="Create and select a self-contained literary project.")
    project_create.add_argument("parent_directory")
    project_create.add_argument("--title", required=True)
    project_create.add_argument("--folder-name", default="")
    project_create.add_argument("--work-type", default="novel")
    project_create.add_argument("--target-length", type=int, default=30000)
    project_create.add_argument("--target-chapters", type=int, default=0)
    project_create.add_argument("--target-scenes", type=int, default=0)
    project_create.add_argument("--premise", default="")
    project_create.add_argument("--genre", default="")
    direction = sub.add_parser("direction-add", help="Record a user creative direction for future Agent tasks.")
    direction.add_argument("project")
    direction.add_argument("message")

    prepare = sub.add_parser("task-prepare", help="Open a formal task and create an isolated Agent workspace.")
    _task_arguments(prepare)

    run = sub.add_parser("task-run", help="Run one formal task through a selected platform Agent runtime.")
    _task_arguments(run)

    worker = sub.add_parser("agent-worker-once", help="Issue and run the next task for one formal route.")
    _task_arguments(worker, include_task_id=False)

    transaction_status = sub.add_parser(
        "scene-transaction-status",
        help="Inspect lean scene transactions without changing project state.",
    )
    transaction_status.add_argument("project")
    transaction_status.add_argument("--scene", default="")
    transaction_status.add_argument("--transaction-id", default="")
    transaction_status.add_argument("--limit", type=int, default=20)
    transaction_prepare = sub.add_parser(
        "scene-transaction-prepare",
        help="Prepare one recoverable lean scene transaction.",
    )
    transaction_prepare.add_argument("project")
    transaction_prepare.add_argument("scene")
    _scene_transaction_mode(transaction_prepare)
    transaction_run = sub.add_parser(
        "scene-transaction-run",
        help="Run an existing lean scene transaction through production state logic.",
    )
    transaction_run.add_argument("project")
    transaction_run.add_argument("transaction_id")
    transaction_run.add_argument("--max-steps", type=int, default=12)
    transaction_run.add_argument("--steward-approved", action="store_true")
    transaction_resume = sub.add_parser(
        "scene-transaction-resume",
        help="Resume one blocked or interrupted lean scene transaction.",
    )
    transaction_resume.add_argument("project")
    transaction_resume.add_argument("transaction_id")

    serve = sub.add_parser("serve", help="Start the local Studio API and frontend.")
    serve.add_argument("--host", default="")
    serve.add_argument("--port", type=int, default=0)
    # The native shell passes this even though the Python process only uses it
    # for lifecycle diagnostics today.  Keeping it in the public parser makes
    # frozen sidecars and source runs use the same command contract.
    serve.add_argument("--parent-pid", type=int, default=0)
    serve.add_argument("--ready-file", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    if args.command == "config-init":
        path = save_config(config)
        print(f"config: {path}")
        print("model_credentials: disabled")
        return 0

    if args.command == "doctor":
        core = CoreBridge(config).doctor()
        payload = {
            "version": __version__,
            "config": str(default_config_path()),
            "engine": {
                "available": core.returncode == 0,
                "mode": "embedded",
                "detail": core.stderr.strip() if core.returncode else "ready",
            },
            "agent_runners": agent_runner_status(config),
            "model_connections": model_connection_status(config),
            "model_connection_policy": "runner-managed",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if core.returncode == 0 else 1

    if args.command == "project-list":
        print(json.dumps(list_projects(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "runner-probe":
        result = probe_agent_runner(config, args.runner, model=args.model, timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ready" else 1

    if args.command == "prompt-eval":
        options = {
            "config": config,
            "live": bool(args.live),
            "runner_id": args.runner,
            "model": args.model,
            "timeout": args.timeout,
        }
        report = write_prompt_evaluation(Path(args.output), **options) if args.output else evaluate_prompt_assets(**options)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1

    if args.command == "project-open":
        print(json.dumps(register_project(Path(args.project)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "project-create":
        result = create_project(
            parent_directory=args.parent_directory,
            title=args.title,
            folder_name=args.folder_name,
            work_type=args.work_type,
            target_length=args.target_length,
            target_chapters=args.target_chapters,
            target_scenes=args.target_scenes,
            premise=args.premise,
            genre=args.genre,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "direction-add":
        print(json.dumps(record_direction(Path(args.project), args.message), ensure_ascii=False, indent=2))
        return 0

    if args.command in {"task-prepare", "task-run", "agent-worker-once"}:
        worker = AgentWorker(config)
        if args.command == "task-prepare":
            task, sandbox, terminal = worker.prepare(
                Path(args.project),
                route=args.route,
                runtime_id=args.runtime,
                task_id=getattr(args, "task_id", ""),
                scene=args.scene,
            )
            if terminal:
                print(json.dumps(terminal.as_dict(), ensure_ascii=False, indent=2))
                return 0
            assert task is not None and sandbox is not None
            print(
                json.dumps(
                    {
                        "status": "prepared",
                        "task_id": task.task_id,
                        "runtime": args.runtime,
                        "run_root": str(sandbox.run_root),
                        "workspace": str(sandbox.workspace),
                        "prompt": str(sandbox.prompt_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        result = worker.run_once(
            Path(args.project),
            route=args.route,
            runtime_id=args.runtime,
            task_id=getattr(args, "task_id", ""),
            scene=args.scene,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status in {"complete", "route_ready", "waiting_host_agent", "waiting_human"} else 1

    if args.command.startswith("scene-transaction-"):
        return _scene_transaction_command(args, config)

    if args.command == "serve":
        return _serve_command(parser, args, config)

    parser.error(f"unknown command: {args.command}")
    return 2


def _serve_command(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    config: dict[str, object],
) -> int:
    try:
        import uvicorn
    except ImportError as exc:
        parser.error("serve requires pip install -e .[api]")
        raise AssertionError from exc
    server = config.get("server", {})
    server = server if isinstance(server, dict) else {}
    host = args.host or str(server.get("host") or "127.0.0.1")
    # A desktop ready-file request deliberately preserves port zero so the OS
    # can select a conflict-free sidecar port.
    port = args.port if args.ready_file or args.port else int(server.get("port") or 8791)
    try:
        _validate_serve_binding(host, os.environ.get("LES_API_TOKEN", ""))
    except ValueError as exc:
        parser.error(str(exc))
    # Frozen sidecars cannot reliably resolve Uvicorn's secondary module import.
    from ..api_server import create_app

    application = create_app()
    if args.ready_file:
        import asyncio

        return asyncio.run(
            _serve_with_ready_file(
                uvicorn,
                application,
                host=host,
                port=port,
                ready_file=Path(args.ready_file),
            )
        )
    uvicorn.run(application, host=host, port=port)
    return 0


def _task_arguments(parser: argparse.ArgumentParser, *, include_task_id: bool = True) -> None:
    parser.add_argument("project", help="Literary Engineering work-project directory.")
    parser.add_argument("--route", default="scene-development")
    parser.add_argument(
        "--runtime",
        choices=["host-agent", "claude-code", "codex-cli", "pi-worker"],
        default=DEFAULT_CREATIVE_RUNTIME,
    )
    parser.add_argument("--scene", default="")
    if include_task_id:
        parser.add_argument("--task-id", default="")


def _scene_transaction_mode(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=[item.value for item in SceneExecutionMode],
        default=SceneExecutionMode.STANDARD.value,
    )


def _scene_transaction_command(args: argparse.Namespace, config: dict[str, object]) -> int:
    project = Path(args.project).expanduser().resolve()
    if not (project / "project.yaml").is_file():
        raise FileNotFoundError(f"Literary project not found: {project}")
    container = resolve_application_container(config, None)
    repository = SceneTransactionRepository(container.ports.persistence.unit_of_work)
    try:
        if args.command == "scene-transaction-status":
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

        data_root = _application_data_root(config)
        bundle = build_lean_scene_runtime(
            config,
            project_root=project,
            data_root=data_root,
            repository=repository,
        )
        if args.command == "scene-transaction-prepare":
            existing = repository.latest_for_scene(str(project), args.scene)
            reused = existing is not None and existing.status is not SceneTransactionStatus.CANCELLED
            transaction = existing if reused else bundle.service.prepare(
                project,
                args.scene,
                mode=SceneExecutionMode(args.mode),
            )
            _print_json({"status": "prepared", "reused": reused, "transaction": transaction.to_dict()})
            return 0
        if args.command == "scene-transaction-resume":
            transaction = _require_transaction_project(repository.load(args.transaction_id), project)
            resumed = bundle.service.resume(transaction.transaction_id)
            _print_json({"status": "resumed", "transaction": resumed.to_dict()})
            return 0
        transaction = _require_transaction_project(repository.load(args.transaction_id), project)
        steps: list[dict[str, object]] = []
        if transaction.status is not SceneTransactionStatus.COMMITTED:
            for _ in range(max(1, min(32, int(args.max_steps)))):
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
    finally:
        container.shutdown()


def _application_data_root(config: dict[str, object]) -> Path:
    application = config.get("application")
    values = application if isinstance(application, dict) else {}
    return Path(str(values.get("data_root") or ".")).expanduser().resolve()


def _require_transaction_project(transaction, project: Path):
    if Path(transaction.project_root).resolve() != project:
        raise ValueError("scene transaction belongs to another project")
    return transaction


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
