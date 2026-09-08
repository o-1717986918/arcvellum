"""Build the current lean-kernel migration evidence report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from literary_engineering_studio.observability.lean_kernel_ab import (
    RouteEvidence,
    compare_routes,
)


DEFAULT_BASELINE = (
    ROOT / "tests" / "fixtures" / "lean_kernel_v2" / "strict_v1_scene_baseline.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare strict-v1 and lean-v2 without changing a project."
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--literary-scores", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    scores = (
        json.loads(args.literary_scores.read_text(encoding="utf-8"))
        if args.literary_scores
        else None
    )
    strict = RouteEvidence(
        route="strict-v1",
        model_calls=int(baseline.get("ideal_model_calls") or 8),
        recoverable_states=int(baseline["state_count"]),
        project_agent_task_files=int(baseline["ideal_agent_task_files"]),
        canon_regressions=int(baseline.get("canon_regressions") or 0),
    )
    lean = RouteEvidence(
        route="lean-v2-standard",
        model_calls=2,
        recoverable_states=5,
        project_agent_task_files=0,
        canon_regressions=0,
    )
    report = compare_routes(strict, lean, literary_scores=scores)
    report["source"] = {
        "strict_baseline": _display_path(args.baseline),
        "lean_contract": "standard scene: create, verify, conditional review, commit",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output.resolve()), **report}, ensure_ascii=False, indent=2))
    return 0 if report["decision"] != "hold" else 2


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


if __name__ == "__main__":
    raise SystemExit(main())
