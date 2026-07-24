"""Maintainer-only compatibility command handlers."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...dify_dsl import DifyDslOptions, build_dify_workflow_dsl
from ...director_agent import build_director_status, run_director_turn
from ...langgraph_adapter import run_literary_graph
from ...model_config import config_path, default_config, load_config, redacted_effective_config, save_config
def handle(args, parser) -> int | None:
    if args.command == "director-chat":
        try:
            result = run_director_turn(
                Path(args.project),
                args.message,
                provider=args.provider,
                auto_execute=not args.no_execute,
                agent_tasks=args.agent_tasks,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"reply: {result.reply}")
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"decision: {result.decision_path}")
        print(f"report: {result.report_path}")
        print(f"agent_run: {result.agent_run_dir}")
        print(f"validation: {result.validation_path}")
        if result.workflow_state_path:
            print(f"workflow_state: {result.workflow_state_path}")
        return 0

    if args.command == "director-status":
        data = build_director_status(Path(args.project), limit=args.limit)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-langgraph":
        try:
            result = run_literary_graph(
                Path(args.project),
                scene=Path(args.scene),
                chapter_id=args.chapter_id,
                target_length=args.target_length,
                include_blocked=args.include_blocked,
                overwrite_draft=args.overwrite_draft,
                generate_candidate=args.generate_candidate,
                promote_candidate=args.promote_candidate,
                agent_review=args.agent_review,
                provider=args.provider,
                thread_id=args.thread_id,
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        print("langgraph_result:")
        for key in sorted(result):
            print(f"{key}: {result[key]}")
        return 0

    if args.command == "serve-api":
        try:
            import uvicorn

            from .api_server import create_app
        except ImportError as exc:
            parser.error(f"serve-api requires optional deps: fastapi, uvicorn, pydantic. {exc}")
        try:
            app = create_app(
                allowed_roots=[Path(item) for item in args.allowed_root],
                api_token=args.api_token or os.environ.get("LEW_API_TOKEN", ""),
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "dify-dsl":
        result = build_dify_workflow_dsl(
            DifyDslOptions(
                output=Path(args.out),
                app_name=args.app_name,
                api_base=args.api_base,
                dsl_version=args.dsl_version,
                default_mode=args.default_mode,
                default_scene=args.default_scene,
                default_chapter_id=args.default_chapter_id,
            )
        )
        print(f"dify_dsl: {result.output_path}")
        print(f"app_name: {result.app_name}")
        print(f"api_base: {result.api_base}")
        print(f"nodes: {result.node_count}")
        print(f"endpoints: {result.endpoint_count}")
        return 0

    if args.command == "config-show":
        data = load_config() if args.raw else redacted_effective_config()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command == "config-init":
        path = config_path()
        if path.exists() and not args.overwrite:
            print(f"config_exists: {path}")
            print("use --overwrite to reset it")
            return 0
        path = save_config(default_config())
        print(f"config: {path}")
        print(json.dumps(redacted_effective_config(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "config-set-profile":
        cfg = load_config()
        profiles = cfg.setdefault("profiles", {})
        profile = dict(profiles.get(args.name, {}))
        if args.api_base:
            profile["api_base"] = args.api_base
        if args.model:
            profile["model"] = args.model
        if args.api_key_env:
            profile["api_key_env"] = args.api_key_env
        if args.temperature is not None:
            profile["temperature"] = args.temperature
        if args.max_tokens is not None:
            profile["max_tokens"] = args.max_tokens
        if args.timeout is not None:
            profile["timeout"] = args.timeout
        profile.setdefault("provider", "http-chat")
        profile.setdefault("api_key_env", "LEW_MODEL_API_KEY")
        profiles[args.name] = profile
        if args.activate or not cfg.get("active_profile"):
            cfg["active_profile"] = args.name
        if args.project_root:
            cfg.setdefault("defaults", {})["project_root"] = args.project_root
        path = save_config(cfg)
        print(f"config: {path}")
        print(json.dumps(redacted_effective_config(), ensure_ascii=False, indent=2))
        return 0

    return None
