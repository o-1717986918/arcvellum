"""Studio command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .config import default_config_path, load_config, save_config
from .core_bridge import CoreBridge
from .model_connections import model_connection_status
from .opencode_binary import install_pinned_opencode
from .project_manager import create_project, list_projects, record_direction, register_project
from .prompt_evaluation import evaluate_prompt_assets, write_prompt_evaluation
from .runner_probe import probe_agent_runner
from .runtimes import agent_runner_status
from .worker import AgentWorker


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
    runner_probe.add_argument("--runner", choices=["opencode", "claude-code", "codex-cli"], required=True)
    runner_probe.add_argument("--model", default="")
    runner_probe.add_argument("--timeout", type=int, default=90)
    opencode_install = sub.add_parser("opencode-install", help="Install and verify the pinned bundled OpenCode Runner.")
    opencode_install.add_argument("--destination", default="")
    prompt_eval = sub.add_parser("prompt-eval", help="Run deterministic and optional live semantic prompt regressions.")
    prompt_eval.add_argument("--output", default="")
    prompt_eval.add_argument("--live", action="store_true")
    prompt_eval.add_argument("--runner", choices=["opencode", "claude-code", "codex-cli"], default="opencode")
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

    serve = sub.add_parser("serve", help="Start the local Studio API and frontend.")
    serve.add_argument("--host", default="")
    serve.add_argument("--port", type=int, default=0)
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

    if args.command == "opencode-install":
        destination = Path(args.destination).expanduser() if args.destination else None
        result = install_pinned_opencode(destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

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

    if args.command == "serve":
        try:
            import uvicorn
        except ImportError as exc:
            parser.error("serve requires pip install -e .[api]")
            raise AssertionError from exc
        server = config.get("server", {}) if isinstance(config.get("server"), dict) else {}
        host = args.host or str(server.get("host") or "127.0.0.1")
        port = args.port or int(server.get("port") or 8791)
        uvicorn.run("literary_engineering_studio.api_server:create_app", host=host, port=port, factory=True)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _task_arguments(parser: argparse.ArgumentParser, *, include_task_id: bool = True) -> None:
    parser.add_argument("project", help="Literary Engineering work-project directory.")
    parser.add_argument("--route", default="scene-development")
    parser.add_argument("--runtime", choices=["opencode", "host-agent", "claude-code", "codex-cli"], default="opencode")
    parser.add_argument("--scene", default="")
    if include_task_id:
        parser.add_argument("--task-id", default="")


if __name__ == "__main__":
    raise SystemExit(main())
