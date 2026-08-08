"""Scene roleplay, branch, and composition command handlers."""

from __future__ import annotations

from pathlib import Path

from ...branch_lab import build_branch_simulation
from ...cli_support import print_agent_task_notice
from ...roleplay_lab import build_roleplay_simulation
from ...scene_composer import build_scene_composition


def handle_simulate_scene(args, parser) -> int:
    result = build_roleplay_simulation(
        Path(args.project),
        scene=Path(args.scene),
        context=Path(args.context) if args.context else None,
        query=args.query,
        rebuild_context=args.rebuild_context,
        output=Path(args.out) if args.out else None,
        agent_mode=args.agent_tasks,
        roleplay_depth=args.roleplay_depth,
    )
    print(f"simulation: {result.output_path}")
    print(f"context: {result.context_path}")
    print(f"scene: {result.scene_id}")
    print(f"characters: {result.character_count}")
    if result.agent_tasks_path:
        print(f"agent_tasks: {result.agent_tasks_path}")
        print_agent_task_notice(
            result.agent_tasks_path,
            project=Path(args.project).resolve(),
        )
    return 0


def handle_branch_simulate(args, parser) -> int:
    try:
        result = build_branch_simulation(
            Path(args.project),
            scene=Path(args.scene),
            context=Path(args.context) if args.context else None,
            query=args.query,
            rebuild_context=args.rebuild_context,
            branch_count=args.branch_count,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
            selection_output=Path(args.selection_out) if args.selection_out else None,
            agent_tasks=args.agent_tasks,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"branch_simulation: {result.output_path}")
    print(f"manifest: {result.manifest_path}")
    print(f"selection: {result.selection_path}")
    if result.agent_tasks_path:
        print(f"agent_tasks: {result.agent_tasks_path}")
        print_agent_task_notice(
            result.agent_tasks_path,
            project=Path(args.project).resolve(),
        )
    print(f"context: {result.context_path}")
    print(f"scene: {result.scene_id}")
    print(f"branches: {result.branch_count}")
    print(f"recommended: {result.recommended_branch}")
    return 0


def handle_compose_scene(args, parser) -> int:
    try:
        result = build_scene_composition(
            Path(args.project),
            scene=Path(args.scene),
            context=Path(args.context) if args.context else None,
            query=args.query,
            rebuild_context=args.rebuild_context,
            branch_manifest=(
                Path(args.branch_manifest) if args.branch_manifest else None
            ),
            branch_selection=(
                Path(args.branch_selection) if args.branch_selection else None
            ),
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
            agent_tasks=args.agent_tasks,
            allow_recommended_branch=args.allow_recommended_branch,
            allow_missing_branch=args.allow_missing_branch,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"composition: {result.output_path}")
    print(f"json: {result.json_path}")
    if result.agent_tasks_path:
        print(f"agent_tasks: {result.agent_tasks_path}")
        print_agent_task_notice(
            result.agent_tasks_path,
            project=Path(args.project).resolve(),
        )
    print(f"context: {result.context_path}")
    print(f"scene: {result.scene_id}")
    print(f"branch: {result.selected_branch}")
    print(f"characters: {result.character_count}")
    print(f"beats: {result.beat_count}")
    return 0


HANDLERS = {
    "simulate-scene": handle_simulate_scene,
    "branch-simulate": handle_branch_simulate,
    "compose-scene": handle_compose_scene,
}
