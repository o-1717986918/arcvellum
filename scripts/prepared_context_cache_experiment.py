"""Run a model-free prepared-context cache micro-benchmark."""

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
from literary_engineering_studio.runtime.context_cache_experiment import (
    run_prepared_context_cache_experiment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure repeated prepared-context reuse in an isolated project "
            "copy without invoking a model or changing production settings."
        )
    )
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_prepared_context_cache_experiment(
        args.project,
        task_id=args.task_id,
        config=load_config(args.config),
        output_path=args.output,
        repetitions=args.repetitions,
    )
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "cache_canary_candidate": report["cache_canary_candidate"],
                "comparison": report["comparison"],
                "criteria": report["criteria"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["cache_canary_candidate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
