"""Asset candidate creation, review, and promotion command handlers."""
from __future__ import annotations

from pathlib import Path

from ...asset_workshop import list_asset_candidates, promote_candidate_asset
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...platform_agent_tasks import (
    write_platform_asset_creation_task, write_platform_asset_review_task,
    write_project_seed_asset_tasks,
)
def handle(args, parser) -> int | None:
    if args.command in {
        "agent-create-character",
        "agent-create-background-story",
        "agent-create-relationship",
        "agent-create-world",
        "agent-create-location",
        "agent-create-organization",
        "agent-create-outline",
        "agent-create-chapter-plan",
        "agent-create-scene-list",
    }:
        try:
            result = write_platform_asset_creation_task(
                Path(args.project).resolve(),
                asset_type=args.asset_type,
                brief=args.brief,
                target_id=args.target_id,
                source=Path(args.source) if args.source else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_creation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_json_path}")
        print(f"expected_report: {result.expected_report_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "asset-create":
        try:
            result = write_platform_asset_creation_task(
                Path(args.project).resolve(),
                asset_type=args.type,
                brief=args.brief,
                target_id=args.target_id,
                source=Path(args.source) if args.source else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_creation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_json_path}")
        print(f"expected_report: {result.expected_report_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "seed-project-assets":
        try:
            results = write_project_seed_asset_tasks(Path(args.project).resolve())
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        for result in results:
            print(f"asset_creation_task: {result.task_path}")
            print(f"expected_candidate: {result.expected_json_path}")
            print(f"expected_report: {result.expected_report_path}")
        print("receiver: platform-agent")
        return 0

    if args.command == "list-candidate-assets":
        for item in list_asset_candidates(Path(args.project), asset_type=args.type):
            print(f"{item['candidate_id']}\t{item['asset_type']}\t{item['status']}\t{item['path']}\t{item['title']}")
        return 0

    if args.command == "review-candidate-asset":
        try:
            result = write_platform_asset_review_task(
                Path(args.project).resolve(),
                candidate_path=Path(args.candidate),
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"asset_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "promote-candidate-asset":
        try:
            result = promote_candidate_asset(
                Path(args.project),
                args.candidate,
                group=args.group,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"promotion: {result.report_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"status: {result.status}")
        for path in result.output_paths:
            print(f"output: {path}")
        return 0

    if args.command in {"promote-character-candidate", "promote-world-candidate", "promote-outline-candidate"}:
        try:
            result = promote_candidate_asset(
                Path(args.project),
                args.candidate,
                group=args.promote_group,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"promotion: {result.report_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"status: {result.status}")
        for path in result.output_paths:
            print(f"output: {path}")
        return 0

    return None
