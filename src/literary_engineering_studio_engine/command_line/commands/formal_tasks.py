"""Formal task lifecycle command handlers."""

from __future__ import annotations

import json
from pathlib import Path

from ...cli_support import (
    print_agent_task_notice,
    print_human_decision_notice,
)
from ...task_contract_audit import build_task_contract_audit
from ...task_registry import (
    advance_workflow,
    complete_task,
    issue_next_task,
    open_task,
    replay_task_contract,
    revert_task_submission,
    submit_task,
)


def handle_task_next(args, parser) -> int:
    try:
        result = issue_next_task(
            Path(args.project),
            route=args.route,
            scene=Path(args.scene) if args.scene else None,
            force=args.force,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"route: {result.route}")
    if result.scene_id:
        print(f"scene: {result.scene_id}")
    if result.current_state:
        print(f"current_state: {result.current_state}")
    if result.task_id:
        print(f"task_id: {result.task_id}")
    if result.task_json_path:
        print(f"task_json: {result.task_json_path}")
    if result.task_markdown_path:
        _print_task_notice(args, result)
    print(f"expected_outputs: {result.expected_output_count}")
    print(f"message: {result.message}")
    return 0


def _print_task_notice(args, result) -> None:
    print(f"task: {result.task_markdown_path}")
    payload = (
        json.loads(result.task_json_path.read_text(encoding="utf-8"))
        if result.task_json_path
        else {}
    )
    project = Path(args.project).resolve()
    if str(payload.get("execution_policy") or "") == "human-required":
        print_human_decision_notice(result.task_markdown_path, project=project)
    else:
        print_agent_task_notice(result.task_markdown_path, project=project)


def handle_task_access(args, parser) -> int:
    try:
        result = (
            open_task(Path(args.project), args.task_id)
            if args.command == "task-open"
            else replay_task_contract(Path(args.project), args.task_id)
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"task_id: {result.task_id}")
    print(f"task_json: {result.task_json_path}")
    print(f"task: {result.task_markdown_path}")
    print(f"route: {result.route}")
    print(f"scene: {result.scene_id or 'n/a'}")
    print(f"current_state: {result.current_state}")
    print(f"expected_outputs: {result.expected_output_count}")
    if args.command == "task-contract-replay":
        print(f"message: {result.message}")
    return 0


def handle_task_submit(args, parser) -> int:
    try:
        result = submit_task(
            Path(args.project),
            args.task_id,
            [Path(item) for item in args.artifacts],
            note=args.note,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"task_id: {result.task_id}")
    print(f"task_json: {result.task_json_path}")
    print(f"submission: {result.submission_path}")
    print(f"artifacts: {result.artifact_count}")
    print(f"message: {result.message}")
    return 0


def handle_task_complete(args, parser) -> int:
    try:
        result = complete_task(
            Path(args.project),
            args.task_id,
            handled_by=args.handled_by,
            notes=args.note,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"task_id: {result.task_id}")
    print(f"task_json: {result.task_json_path}")
    print(f"task: {result.task_markdown_path}")
    print(f"route: {result.route}")
    print(f"scene: {result.scene_id or 'n/a'}")
    print(f"current_state: {result.current_state}")
    print(f"message: {result.message}")
    return 0


def handle_task_revert(args, parser) -> int:
    try:
        result = revert_task_submission(
            Path(args.project),
            args.task_id,
            reason=args.reason,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"task_id: {result.task_id}")
    print(f"message: {result.message}")
    return 0


def handle_task_contract_audit(args, parser) -> int:
    result = build_task_contract_audit(
        Path(args.project),
        output=Path(args.out) if args.out else None,
        json_output=Path(args.json_out) if args.json_out else None,
    )
    print(f"audit: {result.markdown_path}")
    print(f"json: {result.json_path}")
    print(f"tasks: {result.task_count}")
    print(f"errors: {result.error_count}")
    return 0 if result.error_count == 0 else 2


def handle_workflow_advance(args, parser) -> int:
    try:
        result = advance_workflow(Path(args.project), route=args.route)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"status: {result.status}")
    print(f"route: {result.route}")
    print(f"workflow_state: {result.task_markdown_path}")
    print(f"json: {result.task_json_path}")
    print(f"message: {result.message}")
    return 0


HANDLERS = {
    "task-next": handle_task_next,
    "task-open": handle_task_access,
    "task-contract-replay": handle_task_access,
    "task-submit": handle_task_submit,
    "task-complete": handle_task_complete,
    "task-revert-submission": handle_task_revert,
    "task-contract-audit": handle_task_contract_audit,
    "workflow-advance": handle_workflow_advance,
}
