from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from literary_engineering_studio.application.demo_distribution import verify_demo_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify bundled ArcVellum demo projects.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--require-work-id", default="")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    directory = args.directory.expanduser().resolve()
    bundles = sorted(directory.glob("*.arcvellum-demo")) if directory.is_dir() else []
    if not bundles:
        if args.allow_missing:
            print(f"No demo bundle found in {directory}; missing bundle is allowed for this build.")
            return 0
        raise SystemExit(f"No authorized demo bundle found in {directory}")
    work_ids: set[str] = set()
    for bundle in bundles:
        result = verify_demo_bundle(bundle)
        if not result.ok:
            raise SystemExit(f"Invalid demo bundle {bundle.name}: {'; '.join(result.errors)}")
        work_ids.add(str(result.manifest.get("work_id") or ""))
        print(f"Verified demo bundle: {bundle.name}")
    if args.require_work_id and args.require_work_id not in work_ids:
        raise SystemExit(f"Required demo work is missing: {args.require_work_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
