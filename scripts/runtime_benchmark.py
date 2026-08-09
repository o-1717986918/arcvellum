"""CLI for ArcVellum runtime benchmark catalogs and historical reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


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
    else:
        payload = build_historical_runtime_report(args.runs_root, limit=max(0, args.limit))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_historical_report_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
