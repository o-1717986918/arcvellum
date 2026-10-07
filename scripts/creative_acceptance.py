"""Opt-in isolated continuous-scene acceptance; uses the configured runtime only."""
from argparse import ArgumentParser
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "src"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from tests.acceptance.creative_cases import CASES
from tests.acceptance.creative_runner import run_batch
from tests.acceptance.creative_comparisons import tone_comparison, independent_roles
from tests.acceptance.creative_report import readable_report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--action", choices=['scenes','tone','roles','report'], default='scenes')
    parser.add_argument("--scene",default='scene_0001')
    parser.add_argument("--revision",type=int)
    parser.add_argument("--comparison-tag",default='same-prose')
    parser.add_argument("--role-context",default='')
    parser.add_argument("--tone", action="store_true")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--max-calls", type=int, default=80)
    parser.add_argument("--max-minutes", type=int, default=45)
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument("--confirm-live-model", action="store_true")
    args = parser.parse_args()
    if not args.confirm_live_model and args.action!='report':
        parser.error("--confirm-live-model is required for paid model execution")
    if not args.variant.replace("-", "").replace("_", "").isalnum() or min(args.max_calls, args.max_minutes, args.max_revisions) < 1:
        parser.error("variant and positive budgets are required")
    if args.action=='report':
        print(readable_report(args.output.resolve()));return 0
    if args.action in ('tone','roles'):
        action=tone_comparison if args.action=='tone' else independent_roles
        kwargs={'scene_id':args.scene,'revision':args.revision,'comparison_tag':args.comparison_tag} if args.action=='tone' else {'role_context':args.role_context}
        report=action(args.config.resolve(),args.output.resolve(),args.case,args.variant,**kwargs)
        print(json.dumps({'cost':report['cost'],'action':args.action},ensure_ascii=False));return 0
    report = run_batch(args.config.resolve(), args.output.resolve(), args.case, variant=args.variant,
        tone=args.tone, profile_path=args.profile, max_calls=args.max_calls,
        max_minutes=args.max_minutes, max_revisions=args.max_revisions)
    print(json.dumps({"status": report["status"], "cost": report["cost"],
        "report": str(args.output.resolve() / args.case / args.variant / "acceptance.json")}, ensure_ascii=False))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
