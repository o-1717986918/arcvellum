"""Maintainer-only entrypoint for one audited legacy context migration."""

from __future__ import annotations

import argparse
from pathlib import Path

from literary_engineering_studio_engine.literary.scene.promotion.context_migration import (
    migrate_legacy_historical_context,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--snapshot-prompt", required=True)
    parser.add_argument("--packet-source", required=True)
    parser.add_argument("--trace-source", required=True)
    args = parser.parse_args()
    result = migrate_legacy_historical_context(
        Path(args.project),
        args.scene,
        snapshot_prompt=Path(args.snapshot_prompt),
        packet_source=Path(args.packet_source),
        trace_source=Path(args.trace_source),
    )
    print(f"archive: {result.archive_manifest}")
    print(f"receipt: {result.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
