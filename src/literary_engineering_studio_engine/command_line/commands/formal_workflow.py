"""Formal protocol, status, audit, and workflow projection handlers."""

from __future__ import annotations

from pathlib import Path

from ...agent_task_status import build_agent_task_status, build_route_audit
from ...protocol import (
    protocol_to_json,
    render_protocol,
    render_protocol_list,
    resolve_protocol_route,
)
from ...task_registry import build_workflow_events
from ...workflow_contract import validate_workflow_contract
from ...workflow_dashboard import build_workflow_dashboard
from ...workflow_state import build_workflow_state, next_scene_workflow_state


def handle_protocol(args, parser) -> int:
    if not args.route:
        print(protocol_to_json(None) if args.json else render_protocol_list(), end="")
        return 0
    try:
        route = resolve_protocol_route(args.route)
    except KeyError as exc:
        parser.error(str(exc))
    print(protocol_to_json(route) if args.json else render_protocol(route), end="")
    return 0


def handle_agent_task_status(args, parser) -> int:
    try:
        result = build_agent_task_status(
            Path(args.project),
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
        )
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


def handle_route_audit(args, parser) -> int:
    try:
        project = Path(args.project).resolve()
        route = args.route or "scene-development"
        result = build_route_audit(
            project,
            route=route,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
        )
        state = _route_workflow_state(project, route, args.full_state)
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


def _route_workflow_state(project: Path, route: str, full_state: bool):
    current_scene = (
        next_scene_workflow_state(project)
        if route == "scene-development" and not full_state
        else None
    )
    if current_scene and current_scene.get("scene"):
        return build_workflow_state(
            project,
            route=route,
            scene=str(current_scene["scene"]),
            output=Path("workflow/runtime_choices/route-audit-scene-development.md"),
            json_output=Path("workflow/runtime_choices/route-audit-scene-development.json"),
        )
    return build_workflow_state(project, route=route)


def handle_workflow_state(args, parser) -> int:
    try:
        result = build_workflow_state(
            Path(args.project),
            route=args.route,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
        )
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


def handle_workflow_events(args, parser) -> int:
    try:
        result = build_workflow_events(
            Path(args.project),
            output=Path(args.out) if args.out else None,
        )
    except FileNotFoundError as exc:
        parser.error(str(exc))
    print(f"events: {result.events_path}")
    print(f"report: {result.markdown_path}")
    print(f"count: {result.event_count}")
    return 0


def handle_workflow_dashboard(args, parser) -> int:
    try:
        result = build_workflow_dashboard(
            Path(args.project),
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
            html_output=Path(args.html_out) if args.html_out else None,
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


def handle_workflow_validate(args, parser) -> int:
    try:
        result = validate_workflow_contract(
            Path(args.project),
            route=args.route,
            state_path=Path(args.state) if args.state else None,
            output=Path(args.out) if args.out else None,
            json_output=Path(args.json_out) if args.json_out else None,
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


HANDLERS = {
    "protocol": handle_protocol,
    "agent-task-status": handle_agent_task_status,
    "route-audit": handle_route_audit,
    "workflow-state": handle_workflow_state,
    "workflow-events": handle_workflow_events,
    "workflow-dashboard": handle_workflow_dashboard,
    "workflow-validate": handle_workflow_validate,
}
