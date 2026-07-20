"""Studio command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .config import default_config_path, load_config, save_config
from .core_bridge import CoreBridge
from .runtimes import runtime_status
from .worker import AgentWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="les",
        description="Literary Engineering Studio: CLI-bound Agent Worker and platform-agent adapters.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("config-init", help="Write a credential-free Studio configuration.")
    sub.add_parser("doctor", help="Check the core CLI and installed Agent runtimes.")

    prepare = sub.add_parser("task-prepare", help="Open a core task and create an isolated Agent workspace.")
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
            "core": {
                "available": core.returncode == 0,
                "repo": str(CoreBridge(config).core_repo),
                "detail": core.stderr.strip() if core.returncode else "ready",
            },
            "runtimes": runtime_status(config),
            "model_provider": "not part of this project",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if core.returncode == 0 else 1

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
    parser.add_argument("--runtime", choices=["host-agent", "claude-code", "codex-cli"], default="host-agent")
    parser.add_argument("--scene", default="")
    if include_task_id:
        parser.add_argument("--task-id", default="")


if __name__ == "__main__":
    raise SystemExit(main())
