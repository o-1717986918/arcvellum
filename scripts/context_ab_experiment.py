"""Run one isolated, same-model shadow/bounded context experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from literary_engineering_studio.application.config import load_config
from literary_engineering_studio.runtime.context_ab import (
    run_context_ab_experiment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a real Agent task against isolated shadow and bounded "
            "project copies without changing the source project."
        )
    )
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--runtime", default="opencode")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_context_ab_experiment(
        args.project,
        task_id=args.task_id,
        runtime_id=args.runtime,
        config=load_config(args.config),
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "canary_candidate": report["canary_candidate"],
                "comparison": report["comparison"],
                "criteria": report["criteria"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["canary_candidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
