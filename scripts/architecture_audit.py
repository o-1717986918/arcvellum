"""Command-line entry point and stable imports for the architecture audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .architecture_audit_core import (
        audit_repository,
        baseline_from_report,
        compare_with_baseline,
        load_baseline,
        scan_dependency_violations,
    )
else:
    from architecture_audit_core import (
        audit_repository,
        baseline_from_report,
        compare_with_baseline,
        load_baseline,
        scan_dependency_violations,
    )

__all__ = [
    "audit_repository",
    "compare_with_baseline",
    "load_baseline",
    "scan_dependency_violations",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit ArcVellum architecture boundaries and debt budgets.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline_path = (args.baseline or root / "architecture" / "quality-baseline.json").resolve()
    report = audit_repository(root)
    if args.write_baseline:
        if report["dependency_violations"] or report["parse_errors"]:
            for item in [*report["dependency_violations"], *report["parse_errors"]]:
                print(item)
            return 1
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(baseline_from_report(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"architecture baseline written: {baseline_path}")
        return 0
    violations = compare_with_baseline(report, load_baseline(baseline_path))
    if args.json:
        print(json.dumps({"ok": not violations, "violations": violations, "report": report}, ensure_ascii=False, indent=2))
    elif violations:
        print("Architecture audit failed:")
        for item in violations:
            print(f"- {item}")
    else:
        print(
            "Architecture audit passed: "
            f"{len(report['oversized_files'])} file debts, "
            f"{len(report['oversized_functions'])} function debts, "
            f"{len(report['import_cycles'])} existing cycles."
        )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
