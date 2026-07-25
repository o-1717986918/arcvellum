"""Create a disposable ArcVellum project for browser-scale verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.narrative_visual_fixture import materialize_narrative_visual_fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a graph-rich ArcVellum visual fixture.")
    parser.add_argument("target", type=Path)
    parser.add_argument("--scenes", type=int, choices=(100, 300, 1000), default=1000)
    args = parser.parse_args(argv)
    report = materialize_narrative_visual_fixture(args.target, args.scenes)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
