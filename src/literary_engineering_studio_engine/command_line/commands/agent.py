"""Low-level Agent task construction and maintainer runtime commands."""
from __future__ import annotations

from pathlib import Path

from ...agent_provider import run_agent_task
from ...agent_schema import repair_agent_run, validate_agent_run
from ...cli_support import read_prompt_arg as _read_prompt_arg
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...platform_agent_tasks import (
    write_platform_canon_review_task, write_platform_committee_task, write_platform_json_task,
    write_platform_patch_plan_task, write_platform_scene_review_task,
    write_platform_style_prompt_task,
)
def handle(args, parser) -> int | None:
    if args.command == "agent-run":
        project = Path(args.project)
        try:
            system_prompt = _read_prompt_arg(project, args.system, args.system_text, "system")
            user_prompt = _read_prompt_arg(project, args.user, args.user_text, "user")
            result = run_agent_task(
                project,
                agent_id=args.agent_id,
                task=args.task,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                provider=args.provider,
                output_dir=Path(args.out_dir) if args.out_dir else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"provider: {result.provider}")
        print(f"parse_status: {result.parse_status}")
        print(f"input: {result.input_path}")
        print(f"raw_output: {result.raw_output_path}")
        print(f"parsed_output: {result.parsed_output_path}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-validate":
        try:
            result = validate_agent_run(
                Path(args.project),
                run_id=args.run_id,
                run_dir=Path(args.run_dir) if args.run_dir else None,
                schema_name=args.schema,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"schema: {result.schema_name}")
        print(f"status: {result.status}")
        print(f"errors: {result.error_count}")
        print(f"warnings: {result.warning_count}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-repair":
        try:
            result = repair_agent_run(
                Path(args.project),
                run_id=args.run_id,
                run_dir=Path(args.run_dir) if args.run_dir else None,
                schema_name=args.schema,
                provider=args.provider,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"schema: {result.schema_name}")
        print(f"status: {result.status}")
        print(f"repair_run: {result.repair_run_dir}")
        print(f"validation: {result.validation_path}")
        return 0

    if args.command == "agent-review-scene":
        try:
            root = Path(args.project).resolve()
            scene_path = Path(args.scene)
            scene_path = scene_path if scene_path.is_absolute() else root / scene_path
            draft_path = Path(args.draft) if args.draft else root / "drafts" / "scenes" / f"{scene_path.stem}.md"
            draft_path = draft_path if draft_path.is_absolute() else root / draft_path
            result = write_platform_scene_review_task(
                root,
                scene_path=scene_path,
                draft_path=draft_path,
                report_path=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
                materialization_scope=args.materialization_scope,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_scene_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        _print_agent_task_notice(result.task_path, project=root)
        return 0

    if args.command == "agent-canon-review":
        try:
            result = write_platform_canon_review_task(Path(args.project).resolve())
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_canon_review_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "agent-build-json":
        try:
            result = write_platform_json_task(
                Path(args.project).resolve(),
                schema_name=args.schema,
                task=args.task,
                source=Path(args.source) if args.source else None,
                target=args.target,
                output_dir=Path(args.out_dir) if args.out_dir else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"json_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "agent-plan-patch":
        try:
            result = write_platform_patch_plan_task(
                Path(args.project).resolve(),
                target=args.target,
                source=Path(args.source) if args.source else None,
                report_path=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"patch_plan_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "agent-style-prompt":
        try:
            result = write_platform_style_prompt_task(
                Path(args.profile_dir),
                output=Path(args.out) if args.out else None,
                json_path=Path(args.json_out) if args.json_out else None,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"style_prompt_task: {result.task_path}")
        print(f"expected_style_prompt: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path)
        return 0

    if args.command == "agent-committee":
        try:
            root = Path(args.project).resolve()
            source = Path(args.source) if args.source else None
            if source and not source.is_absolute():
                source = root / source
            result = write_platform_committee_task(
                root,
                subject=args.subject,
                source=source,
            )
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"agent_committee_task: {result.task_path}")
        print(f"expected_report: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    return None
