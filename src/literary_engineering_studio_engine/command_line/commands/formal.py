"""State-machine-first formal host command handlers."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from ...agent_task_status import build_agent_task_status, build_route_audit
from ...cli_parser import build_parser
from ...cli_support import (
    print_agent_task_notice as _print_agent_task_notice,
    print_human_decision_notice as _print_human_decision_notice,
    render_formal_help as _render_formal_help,
)
from ...formal_mode import bypass_hits, formal_bypass_message
from ...prompt_registry import (
    list_prompt_assets, render_prompt_preview, render_prompt_registry_list,
    render_prompt_registry_validation, resolve_skill_root, resolve_prompt_asset,
    validate_prompt_registry,
)
from ...protocol import protocol_to_json, render_protocol, render_protocol_list, resolve_protocol_route
from ...task_contract_audit import build_task_contract_audit
from ...task_registry import (
    advance_workflow, build_workflow_events, complete_task, issue_next_task, open_task,
    replay_task_contract, revert_task_submission, submit_task,
)
from ...workflow_contract import validate_workflow_contract
from ...workflow_dashboard import build_workflow_dashboard
from ...workflow_state import build_workflow_state, next_scene_workflow_state


def _handle_task_access(args, parser) -> int:
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


def handle(args, parser) -> int | None:
    if args.command == "formal-help":
        print(_render_formal_help(args.project, args.route), end="")
        return 0

    if args.command == "help-all":
        print(build_parser(full_help=True).format_help(), end="")
        return 0

    hits = bypass_hits(vars(args))
    if hits:
        print(formal_bypass_message(hits, surface=f"lew {args.command}"), file=sys.stderr)
        return 2

    if args.command == "protocol":
        if not args.route:
            print(protocol_to_json(None) if args.json else render_protocol_list(), end="")
            return 0
        try:
            route = resolve_protocol_route(args.route)
        except KeyError as exc:
            parser.error(str(exc))
        print(protocol_to_json(route) if args.json else render_protocol(route), end="")
        return 0

    if args.command == "agent-task-status":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_agent_task_status(Path(args.project), output=out, json_output=json_out)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"agent_task_status: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"tasks: {result.task_count}")
        print(f"pending: {result.pending_count}")
        print(f"partial: {result.partial_count}")
        print(f"complete: {result.complete_count}")
        print(f"missing_expected: {result.missing_expected_count}")
        return 0

    if args.command == "route-audit":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            project = Path(args.project).resolve()
            route = args.route or "scene-development"
            result = build_route_audit(project, route=route, output=out, json_output=json_out)
            current_scene = next_scene_workflow_state(project) if route == "scene-development" and not args.full_state else None
            if current_scene and current_scene.get("scene"):
                state = build_workflow_state(
                    project,
                    route=route,
                    scene=str(current_scene["scene"]),
                    output=Path("workflow/runtime_choices/route-audit-scene-development.md"),
                    json_output=Path("workflow/runtime_choices/route-audit-scene-development.json"),
                )
            else:
                state = build_workflow_state(project, route=route)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"route_audit: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"workflow_state: {state.markdown_path}")
        print(f"workflow_state_json: {state.json_path}")
        print(f"route: {result.route}")
        print(f"gates: {result.gate_count}")
        print(f"blocking: {result.blocking_count}")
        print(f"warnings: {result.warning_count}")
        print(f"pending_tasks: {result.pending_task_count}")
        return 0

    if args.command == "workflow-state":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_workflow_state(Path(args.project), route=args.route, output=out, json_output=json_out)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"workflow_state: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"route: {result.route}")
        print(f"scenes: {result.scene_count}")
        print(f"ready: {result.ready_count}")
        print(f"blocked: {result.blocked_count}")
        print(f"next_actions: {result.next_action_count}")
        return 0

    if args.command == "task-next":
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
            print(f"task: {result.task_markdown_path}")
            task_payload = json.loads(result.task_json_path.read_text(encoding="utf-8")) if result.task_json_path else {}
            if str(task_payload.get("execution_policy") or "") == "human-required":
                _print_human_decision_notice(result.task_markdown_path, project=Path(args.project).resolve())
            else:
                _print_agent_task_notice(result.task_markdown_path, project=Path(args.project).resolve())
        print(f"expected_outputs: {result.expected_output_count}")
        print(f"message: {result.message}")
        return 0

    if args.command in {"task-open", "task-contract-replay"}:
        return _handle_task_access(args, parser)

    if args.command == "task-submit":
        try:
            result = submit_task(Path(args.project), args.task_id, [Path(item) for item in args.artifacts], note=args.note)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"status: {result.status}")
        print(f"task_id: {result.task_id}")
        print(f"task_json: {result.task_json_path}")
        print(f"submission: {result.submission_path}")
        print(f"artifacts: {result.artifact_count}")
        print(f"message: {result.message}")
        return 0

    if args.command == "task-complete":
        try:
            result = complete_task(Path(args.project), args.task_id, handled_by=args.handled_by, notes=args.note)
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

    if args.command == "task-revert-submission":
        try:
            result = revert_task_submission(Path(args.project), args.task_id, reason=args.reason)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"status: {result.status}")
        print(f"task_id: {result.task_id}")
        print(f"message: {result.message}")
        return 0

    if args.command == "task-contract-audit":
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

    if args.command == "workflow-advance":
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

    if args.command == "workflow-events":
        out = Path(args.out) if args.out else None
        try:
            result = build_workflow_events(Path(args.project), output=out)
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"events: {result.events_path}")
        print(f"report: {result.markdown_path}")
        print(f"count: {result.event_count}")
        return 0

    if args.command == "workflow-dashboard":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        html_out = Path(args.html_out) if args.html_out else None
        try:
            result = build_workflow_dashboard(
                Path(args.project),
                output=out,
                json_output=json_out,
                html_output=html_out,
            )
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"workflow_dashboard: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"html: {result.html_path}")
        print(f"routes: {result.route_count}")
        print(f"blocking: {result.blocking_count}")
        print(f"pending_tasks: {result.pending_task_count}")
        print(f"next_actions: {result.next_action_count}")
        return 0

    if args.command == "workflow-validate":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        state_path = Path(args.state) if args.state else None
        try:
            result = validate_workflow_contract(
                Path(args.project),
                route=args.route,
                state_path=state_path,
                output=out,
                json_output=json_out,
            )
        except FileNotFoundError as exc:
            parser.error(str(exc))
        print(f"status: {result.status}")
        print(f"workflow_contract: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"state: {result.state_path}")
        print(f"events: {result.events_path}")
        print(f"errors: {result.error_count}")
        print(f"warnings: {result.warning_count}")
        return 0

    if args.command == "prompt-registry-list":
        try:
            skill_root = Path(args.skill_root) if args.skill_root else None
            if args.json:
                root = resolve_skill_root(skill_root)
                assets = list_prompt_assets(root)
                print(json.dumps([asset.to_dict(root) for asset in assets], ensure_ascii=False, indent=2))
            else:
                print(render_prompt_registry_list(skill_root), end="")
        except FileNotFoundError as exc:
            parser.error(str(exc))
        return 0

    if args.command == "prompt-registry-validate":
        try:
            skill_root = Path(args.skill_root) if args.skill_root else None
            result = validate_prompt_registry(skill_root, include_task_registry=not args.no_task_registry)
            if args.json:
                print(
                    json.dumps(
                        {
                            "schema": "literary-engineering-workbench/prompt-registry-validation/v0.1",
                            "skill_root": str(result.skill_root),
                            "status": "pass" if result.ok else "fail",
                            "asset_count": len(result.assets),
                            "task_prompt_id_count": len(result.task_prompt_ids),
                            "errors": result.errors,
                            "warnings": result.warnings,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(render_prompt_registry_validation(result), end="")
            if not result.ok:
                return 1
        except FileNotFoundError as exc:
            parser.error(str(exc))
        return 0

    if args.command == "prompt-preview":
        try:
            skill_root = Path(args.skill_root) if args.skill_root else None
            result = resolve_prompt_asset(args.prompt_asset_id, skill_root)
            if args.json:
                print(
                    json.dumps(
                        {
                            "schema": "literary-engineering-workbench/prompt-preview/v0.1",
                            "requested_id": result.requested_id,
                            "status": result.message,
                            "exact": result.exact,
                            "asset": result.asset.to_dict(result.skill_root) if result.asset else None,
                            "body": result.asset.body if result.asset else "",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(render_prompt_preview(result), end="")
            if result.asset is None:
                return 1
        except FileNotFoundError as exc:
            parser.error(str(exc))
        return 0

    return None
