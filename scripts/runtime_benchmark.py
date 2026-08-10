"""CLI for ArcVellum runtime benchmark catalogs and historical reports."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from literary_engineering_studio.observability.runtime_benchmark import (
    build_historical_runtime_report,
    load_benchmark_catalog,
    reconstruct_benchmark_case,
    render_historical_report_markdown,
)
from literary_engineering_studio.observability.runtime_benchmark_live import run_live_benchmark
from literary_engineering_studio.application.config import load_config


DEFAULT_CATALOG = ROOT / "tests" / "fixtures" / "runtime_benchmarks" / "catalog.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build content-safe ArcVellum runtime benchmark evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog", help="Validate and summarize the benchmark catalog.")
    catalog.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)

    reconstruct = subparsers.add_parser("reconstruct", help="Rebuild one ready benchmark case.")
    reconstruct.add_argument("case_id")
    reconstruct.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    reconstruct.add_argument("--destination", type=Path, required=True)

    historical = subparsers.add_parser("historical", help="Create a sanitized report from local run artifacts.")
    historical.add_argument("--runs-root", type=Path, required=True)
    historical.add_argument("--output", type=Path, required=True)
    historical.add_argument("--markdown", type=Path)
    historical.add_argument("--limit", type=int, default=0)

    live = subparsers.add_parser("live", help="Run one explicit live-model smoke benchmark.")
    live.add_argument("case_id")
    live.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    live.add_argument("--runtime", default="opencode")
    live.add_argument("--runner-executable", default="")
    live.add_argument("--runner-entrypoint", default="")
    live.add_argument("--runner-model", default="")
    live.add_argument("--runner-auth-path", default="")
    live.add_argument("--runner-thinking", default="low")
    live.add_argument("--timeout-seconds", type=int, default=300)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument(
        "--workdir",
        type=Path,
        help="Retain the reconstructed benchmark project and run artifacts in this directory.",
    )
    live.add_argument(
        "--confirm-live-model",
        action="store_true",
        help="Acknowledge that this command invokes the selected live model.",
    )
    live.add_argument(
        "--confirm-experimental-runner",
        action="store_true",
        help="Acknowledge that the selected Pi runtime is an unsupported, unpackaged experiment.",
    )

    args = parser.parse_args(argv)
    if args.command == "catalog":
        cases = load_benchmark_catalog(args.catalog)
        payload = {
            "schema": "arcvellum/runtime-benchmark-catalog-summary/v1",
            "case_count": len(cases),
            "ready_count": sum(item.availability == "ready" for item in cases),
            "cases": [
                {
                    "case_id": item.case_id,
                    "benchmark_class": item.benchmark_class,
                    "availability": item.availability,
                    "route": item.route,
                    "expected_state": item.expected_state,
                }
                for item in cases
            ],
        }
    elif args.command == "reconstruct":
        cases = {item.case_id: item for item in load_benchmark_catalog(args.catalog)}
        if args.case_id not in cases:
            parser.error(f"unknown benchmark case: {args.case_id}")
        payload = reconstruct_benchmark_case(cases[args.case_id], args.destination).safe_projection()
    elif args.command == "historical":
        payload = build_historical_runtime_report(args.runs_root, limit=max(0, args.limit))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_historical_report_markdown(payload), encoding="utf-8")
    else:
        if not args.confirm_live_model:
            parser.error("live benchmark requires --confirm-live-model")
        runtime_config = None
        if args.runtime in {"pi-rpc", "pi-worker"}:
            if not args.confirm_experimental_runner:
                parser.error(f"{args.runtime} benchmark requires --confirm-experimental-runner")
            if not args.runner_executable or not args.runner_entrypoint or not args.runner_model:
                parser.error(f"{args.runtime} benchmark requires executable, entrypoint, and model")
            runtime_config = load_config()
            settings = runtime_config.setdefault("agent_runners", {}).setdefault(args.runtime, {})
            settings.update(
                {
                    "enabled": True,
                    "executable": args.runner_executable,
                    "entrypoint": args.runner_entrypoint,
                    "model": args.runner_model,
                    "experiment_only": True,
                    "experiment_authorized": True,
                }
            )
            if args.runtime == "pi-worker":
                settings.update(
                    {
                        "auth_path": args.runner_auth_path,
                        "thinking": args.runner_thinking,
                    }
                )
                execution_profile = runtime_config.setdefault("worker", {}).setdefault(
                    "execution_profile", {}
                )
                execution_profile.update(
                    {
                        "mode": "enforced",
                        "enforcement": {
                            "enabled": True,
                            "runtimes": ["pi-worker"],
                            "routes": [],
                            "states": [],
                            "task_kinds": [],
                        },
                    }
                )
        cases = {item.case_id: item for item in load_benchmark_catalog(args.catalog)}
        if args.case_id not in cases:
            parser.error(f"unknown benchmark case: {args.case_id}")
        retained = args.workdir is not None
        temporary = (
            args.workdir.expanduser().resolve()
            if retained
            else Path(tempfile.mkdtemp(prefix="arcvellum-runtime-live-"))
        )
        if retained and os.name == "nt" and len(str(temporary)) > 100:
            parser.error(
                "--workdir is too deep for retained Windows run artifacts; choose a short path"
            )
        if retained:
            temporary.mkdir(parents=True, exist_ok=False)
        try:
            payload = run_live_benchmark(
                cases[args.case_id],
                temporary / "project",
                runtime_id=args.runtime,
                timeout_seconds=args.timeout_seconds,
                config=runtime_config,
            )
        finally:
            if not retained:
                shutil.rmtree(temporary, ignore_errors=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
