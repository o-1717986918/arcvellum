"""Run the real-project narrative performance and completeness gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.narrative_visual_performance import benchmark_materialized_narrative


def main() -> int:
    report = benchmark_materialized_narrative()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
