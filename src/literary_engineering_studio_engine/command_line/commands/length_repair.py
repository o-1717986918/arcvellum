"""CLI handler for deterministic whole-work target-length repair planning."""

from __future__ import annotations

from pathlib import Path

from ...literary.planning.length_repair import build_target_length_repair_plan


def handle(args, parser) -> int | None:
    if args.command != "plan-length-repair":
        return None
    try:
        result = build_target_length_repair_plan(
            Path(args.project),
            output=Path(args.out) if args.out else None,
            markdown_output=Path(args.md_out) if args.md_out else None,
        )
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"repair_json: {result.json_path}")
    print(f"repair_markdown: {result.markdown_path}")
    print(f"shortfall_chinese_chars: {result.shortfall_chinese_chars}")
    print(f"allocated_chinese_chars: {result.allocated_chinese_chars}")
    print(f"scenes: {result.scene_count}")
    print(f"status: {result.status}")
    return 0


__all__ = ["handle"]
