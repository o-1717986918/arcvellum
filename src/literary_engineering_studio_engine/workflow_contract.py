"""Validation contract for the CLI-mediated workflow state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .workflow_state import build_workflow_state


STATE_SCHEMA = "literary-engineering-workbench/formal-route-state/v1"
EVENT_SCHEMA = "literary-engineering-workbench/workflow-event/v1"
TASK_SCHEMA = "literary-engineering-workbench/agent-task/v1"
SUBMISSION_SCHEMA = "literary-engineering-workbench/agent-submission/v1"
COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
ORDER_NEUTRAL_PASS_STEPS = {"scene-word-budget-contract", "reader-experience-contract"}


@dataclass(frozen=True)
class WorkflowContractValidationResult:
    project_root: Path
    status: str
    markdown_path: Path
    json_path: Path
    state_path: Path
    events_path: Path
    error_count: int
    warning_count: int


def validate_workflow_contract(
    project_root: Path,
    *,
    route: str = "scene-development",
    state_path: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
) -> WorkflowContractValidationResult:
    """Validate state/event/task ledgers without advancing the creative route."""

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    if state_path is None:
        state = build_workflow_state(root, route=route)
        resolved_state = state.json_path
    else:
        resolved_state = state_path if state_path.is_absolute() else root / state_path
        if not resolved_state.exists():
            raise FileNotFoundError(f"workflow state JSON not found: {resolved_state}")
    events_path = root / "workflow" / "events" / "task_events.jsonl"
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    state_payload = _read_json(resolved_state)
    _validate_state_payload(state_payload, errors, warnings)
    _validate_step_order(state_payload, errors, warnings)
    _validate_tasks(root, errors, warnings)
    _validate_events(root, events_path, errors, warnings)

    status = "pass" if not errors else "fail"
    markdown_path = _resolve_output(root, output, "workflow", "workflow_contract.md")
    json_path = _resolve_output(root, json_output, "workflow", "workflow_contract.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/workflow-contract-validation/v0.1",
        "generated_at": _now(),
        "status": status,
        "project_root": str(root),
        "state_path": _rel(resolved_state, root),
        "events_path": _rel(events_path, root),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_report(payload), encoding="utf-8")
    return WorkflowContractValidationResult(
        project_root=root,
        status=status,
        markdown_path=markdown_path,
        json_path=json_path,
        state_path=resolved_state,
        events_path=events_path,
        error_count=len(errors),
        warning_count=len(warnings),
    )


def _validate_state_payload(payload: dict[str, Any], errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> None:
    if payload.get("schema") != STATE_SCHEMA:
        errors.append(_issue("workflow_state.schema", f"expected {STATE_SCHEMA}", str(payload.get("schema") or "missing")))
    for field in ("generated_at", "project_root", "route", "summary"):
        if field not in payload:
            errors.append(_issue(f"workflow_state.{field}", "required field missing", "missing"))
    if not isinstance(payload.get("summary"), dict):
        errors.append(_issue("workflow_state.summary", "expected object", type(payload.get("summary")).__name__))
    for field in ("scenes", "source_ingests", "styles", "assets", "audits", "exports"):
        if field in payload and not isinstance(payload.get(field), list):
            errors.append(_issue(f"workflow_state.{field}", "expected list", type(payload.get(field)).__name__))
    if "longform" in payload and not isinstance(payload.get("longform"), dict):
        errors.append(_issue("workflow_state.longform", "expected object", type(payload.get("longform")).__name__))
    if not payload.get("rules"):
        warnings.append(_issue("workflow_state.rules", "rules should document formal route state semantics", "missing"))


def _validate_step_order(payload: dict[str, Any], errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> None:
    containers: list[tuple[str, dict[str, Any]]] = []
    longform = payload.get("longform")
    if isinstance(longform, dict) and longform:
        containers.append(("longform", longform))
    for key in ("scenes", "source_ingests", "styles", "assets", "audits", "exports"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict):
                label = str(item.get("scene_id") or item.get("target_id") or item.get("work_id") or item.get("profile_dir") or item.get("chapter_id") or index)
                containers.append((f"{key}.{label}", item))
    for label, item in containers:
        steps = item.get("steps")
        if not isinstance(steps, list):
            warnings.append(_issue(label, "state item has no steps list", "missing"))
            continue
        first_blocking_index = None
        first_blocking_key = ""
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(_issue(f"{label}.steps[{index}]", "step must be object", type(step).__name__))
                continue
            status = str(step.get("status") or "")
            if not status:
                errors.append(_issue(f"{label}.{step.get('key', index)}.status", "step status missing", "missing"))
            if status != "pass" and first_blocking_index is None:
                first_blocking_index = index
                first_blocking_key = str(step.get("key") or index)
            elif status == "pass" and first_blocking_index is not None:
                if _is_order_neutral_pass_step(step):
                    continue
                errors.append(
                    _issue(
                        f"{label}.{step.get('key', index)}",
                        "downstream step is pass while an upstream gate is still blocking; this suggests an out-of-order or hand-written artifact",
                        f"upstream={first_blocking_key}",
                    )
                )
        if item.get("status") == "ready" and any(isinstance(step, dict) and step.get("status") != "pass" for step in steps):
            errors.append(_issue(label, "state item is ready but at least one step is not pass", "inconsistent"))


def _is_order_neutral_pass_step(step: dict[str, Any]) -> bool:
    """Return true for checks that may pass before upstream creative gates."""

    key = str(step.get("key") or "")
    if key in ORDER_NEUTRAL_PASS_STEPS:
        return True
    if key == "canon-patch-json":
        message = str(step.get("message") or "").lower()
        return "not required" in message or "not_required" in message
    return False


def _validate_tasks(root: Path, errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> None:
    task_dir = root / "workflow" / "tasks"
    if not task_dir.exists():
        warnings.append(_issue("workflow.tasks", "no task registry directory found; route may not have issued tasks yet", "missing"))
        return
    for task_path in sorted(task_dir.glob("*.task.json")):
        payload = _read_json(task_path)
        label = f"task.{task_path.stem}"
        if payload.get("schema") != TASK_SCHEMA:
            errors.append(_issue(f"{label}.schema", f"expected {TASK_SCHEMA}", str(payload.get("schema") or "missing")))
        for field in ("task_id", "status", "route", "current_state", "expected_outputs"):
            if field not in payload:
                errors.append(_issue(f"{label}.{field}", "required field missing", "missing"))
        if str(payload.get("task_id") or "") != task_path.name.removesuffix(".task.json"):
            errors.append(_issue(f"{label}.task_id", "task_id must match task filename", str(payload.get("task_id") or "")))
        status = str(payload.get("status") or "")
        if status not in {"issued", "opened", "submitted", "blocked", "complete"}:
            errors.append(_issue(f"{label}.status", "invalid task status", status or "missing"))
        if status in {"submitted", "complete"}:
            submission = str(payload.get("submission") or "")
            if submission:
                _validate_submission(root, submission, str(payload.get("task_id") or ""), errors)
            elif status == "submitted":
                errors.append(_issue(f"{label}.submission", "submitted task must record submission path", "missing"))
        if status == "complete":
            completion = str(payload.get("completion") or "")
            if not completion:
                errors.append(_issue(f"{label}.completion", "complete task must record completion path", "missing"))
            else:
                _validate_completion(root, completion, str(payload.get("task_id") or ""), errors)


def _validate_submission(root: Path, rel: str, task_id: str, errors: list[dict[str, str]]) -> None:
    path = root / rel
    payload = _read_json(path)
    if payload.get("schema") != SUBMISSION_SCHEMA:
        errors.append(_issue(f"submission.{task_id}.schema", f"expected {SUBMISSION_SCHEMA}", str(payload.get("schema") or "missing")))
    if payload.get("task_id") != task_id:
        errors.append(_issue(f"submission.{task_id}.task_id", "submission task_id mismatch", str(payload.get("task_id") or "")))
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(_issue(f"submission.{task_id}.artifacts", "submission must list artifacts", "missing"))
        return
    missing = [str(item) for item in artifacts if not (root / str(item)).exists()]
    if missing:
        errors.append(_issue(f"submission.{task_id}.artifacts", "submitted artifact path missing", ", ".join(missing)))


def _validate_completion(root: Path, rel: str, task_id: str, errors: list[dict[str, str]]) -> None:
    path = root / rel
    payload = _read_json(path)
    if payload.get("schema") != COMPLETION_SCHEMA:
        errors.append(_issue(f"completion.{task_id}.schema", f"expected {COMPLETION_SCHEMA}", str(payload.get("schema") or "missing")))
    if payload.get("status") not in {"complete", "completed", "done", "handled", "pass"}:
        errors.append(_issue(f"completion.{task_id}.status", "completion marker status is not complete", str(payload.get("status") or "")))
    if payload.get("expected_artifacts_checked") is not True:
        errors.append(_issue(f"completion.{task_id}.expected_artifacts_checked", "must be true", str(payload.get("expected_artifacts_checked"))))


def _validate_events(root: Path, events_path: Path, errors: list[dict[str, str]], warnings: list[dict[str, str]]) -> None:
    if not events_path.exists():
        warnings.append(_issue("workflow.events", "no task event log found; route may not have issued tasks yet", "missing"))
        return
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(_issue(f"workflow.events.line{line_number}", "invalid JSON event", exc.msg))
            continue
        if not isinstance(payload, dict):
            errors.append(_issue(f"workflow.events.line{line_number}", "event must be object", type(payload).__name__))
            continue
        if payload.get("schema") != EVENT_SCHEMA:
            errors.append(_issue(f"workflow.events.line{line_number}.schema", f"expected {EVENT_SCHEMA}", str(payload.get("schema") or "missing")))
        event_type = str(payload.get("event_type") or "")
        if not event_type:
            errors.append(_issue(f"workflow.events.line{line_number}.event_type", "event_type missing", "missing"))
        task_id = str(payload.get("task_id") or "")
        if task_id:
            task_path = root / "workflow" / "tasks" / f"{task_id}.task.json"
            if not task_path.exists():
                errors.append(_issue(f"workflow.events.line{line_number}.task_id", "event references missing task", task_id))
        if not isinstance(payload.get("data"), dict):
            errors.append(_issue(f"workflow.events.line{line_number}.data", "data must be object", type(payload.get("data")).__name__))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _issue(path: str, message: str, actual: str) -> dict[str, str]:
    return {"path": path, "message": message, "actual": actual}


def _render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Workflow Contract Validation",
        "",
        f"- status: `{payload['status']}`",
        f"- state: `{payload['state_path']}`",
        f"- events: `{payload['events_path']}`",
        f"- errors: {payload['error_count']}",
        f"- warnings: {payload['warning_count']}",
        "",
        "## Errors",
        "",
    ]
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    if errors:
        lines.extend(f"- `{item.get('path')}`：{item.get('message')}（{item.get('actual')}）" for item in errors if isinstance(item, dict))
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    if warnings:
        lines.extend(f"- `{item.get('path')}`：{item.get('message')}（{item.get('actual')}）" for item in warnings if isinstance(item, dict))
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
