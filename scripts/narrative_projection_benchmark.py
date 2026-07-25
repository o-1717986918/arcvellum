"""Run the repeatable narrative projection benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.narrative_scale import SCENE_SCALES, benchmark_narrative_projection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure ArcVellum narrative projection scale.")
    parser.add_argument("--scenes", nargs="+", type=int, default=list(SCENE_SCALES))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = benchmark_narrative_projection(args.scenes, repetitions=args.repetitions)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
