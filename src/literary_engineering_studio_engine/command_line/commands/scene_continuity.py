"""Scene character-state and canon patch command handlers."""

from __future__ import annotations

from pathlib import Path

from ...canon_evolver import (
    apply_canon_patch,
    build_canon_patch_backlog,
    build_canon_patch_task,
)
from ...character_state_apply import apply_character_state_patch
from ...character_state_evolver import build_character_state_patch
from ...cli_support import print_agent_task_notice


def handle_state_evolve(args, parser) -> int:
    result = build_character_state_patch(
        Path(args.project),
        scene=Path(args.scene),
        source=Path(args.source) if args.source else None,
        output=Path(args.out) if args.out else None,
        json_output=Path(args.json_out) if args.json_out else None,
        agent_tasks=args.agent_tasks,
    )
    print(f"state_patch: {result.output_path}")
    print(f"json: {result.json_path}")
    if result.agent_tasks_path:
        print(f"agent_tasks: {result.agent_tasks_path}")
        print_agent_task_notice(
            result.agent_tasks_path,
            project=Path(args.project).resolve(),
        )
    print(f"scene: {result.scene_id}")
    print(f"source: {result.source_path}")
    print(f"characters: {result.character_count}")
    print(f"unresolved: {result.unresolved_count}")
    return 0


def handle_canon_evolve(args, parser) -> int:
    result = build_canon_patch_task(
        Path(args.project),
        scene=Path(args.scene),
        source=Path(args.source) if args.source else None,
        output=Path(args.out) if args.out else None,
        json_output=Path(args.json_out) if args.json_out else None,
    )
    print(f"canon_patch: {result.report_path}")
    print(f"json: {result.json_path}")
    print(f"agent_tasks: {result.task_path}")
    print(f"scene: {result.scene_id}")
    print(f"source: {result.source_path}")
    print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
    return 0


def handle_canon_backlog(args, parser) -> int:
    result = build_canon_patch_backlog(
        Path(args.project),
        output=Path(args.out) if args.out else None,
        json_output=Path(args.json_out) if args.json_out else None,
    )
    print(f"canon_backlog: {result.output_path}")
    print(f"json: {result.json_path}")
    print(f"pending: {result.pending_count}")
    print(f"applied: {result.applied_count}")
    return 0


def handle_canon_apply(args, parser) -> int:
    try:
        result = apply_canon_patch(
            Path(args.project),
            patch=Path(args.patch) if args.patch else None,
            approval_run_id=args.approval_run_id,
            allow_unapproved=args.allow_unapproved,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"canon_apply: {result.report_path}")
    print(f"json: {result.json_path}")
    print(f"patch: {result.patch_path}")
    print(f"changelog: {result.changelog_path}")
    print(f"status: {result.status}")
    print(f"items: {result.applied_count}")
    return 0


def handle_state_apply(args, parser) -> int:
    try:
        result = apply_character_state_patch(
            Path(args.project),
            patch=Path(args.patch) if args.patch else None,
            approval_run_id=args.approval_run_id,
            allow_unapproved=args.allow_unapproved,
            allow_unresolved=args.allow_unresolved,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
        )
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"state_apply: {result.report_path}")
    print(f"json: {result.manifest_path}")
    print(f"scene: {result.scene_id}")
    print(f"status: {result.status}")
    print(f"characters: {result.applied_character_count}")
    print(f"updates: {result.update_count}")
    print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
    return 0


HANDLERS = {
    "state-evolve": handle_state_evolve,
    "canon-evolve": handle_canon_evolve,
    "canon-backlog": handle_canon_backlog,
    "canon-apply": handle_canon_apply,
    "state-apply": handle_state_apply,
}
