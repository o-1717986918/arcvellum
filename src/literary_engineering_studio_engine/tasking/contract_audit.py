"""Audit emitted task packages against the engine's semantic contract source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .semantic_contracts import semantic_artifact_contract, semantic_artifact_definition


AUDIT_SCHEMA = "literary-engineering-workbench/task-contract-audit/v0.1"


@dataclass(frozen=True)
class TaskContractAuditResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    task_count: int
    error_count: int


def build_task_contract_audit(
    project_root: Path,
    *,
    output: Path | None = None,
    json_output: Path | None = None,
) -> TaskContractAuditResult:
    root = project_root.resolve()
    task_dir = root / "workflow" / "tasks"
    task_paths = sorted(task_dir.glob("*.task.json")) if task_dir.is_dir() else []
    tasks: list[dict[str, Any]] = []
    for path in task_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            tasks.append({"task": _rel(path, root), "status": "fail", "errors": [f"invalid JSON: {exc}"], "warnings": []})
            continue
        tasks.append(_audit_task(payload if isinstance(payload, dict) else {}, path, root))
    error_count = sum(len(item["errors"]) for item in tasks)
    status = "pass" if error_count == 0 else "fail"
    payload = {
        "schema": AUDIT_SCHEMA,
        "generated_at": _now(),
        "project_root": str(root),
        "status": status,
        "summary": {"task_count": len(tasks), "error_count": error_count},
        "tasks": tasks,
    }
    markdown_path = _resolve(root, output, root / "workflow" / "task_contract_audit.md")
    resolved_json = _resolve(root, json_output, root / "workflow" / "task_contract_audit.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_json.parent.mkdir(parents=True, exist_ok=True)
    resolved_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload, root), encoding="utf-8")
    return TaskContractAuditResult(root, markdown_path, resolved_json, len(tasks), error_count)


def _audit_task(payload: dict[str, Any], path: Path, root: Path) -> dict[str, Any]:
    current_state = str(payload.get("current_state") or "")
    expected = {str(item).replace("\\", "/") for item in payload.get("expected_outputs") or []}
    semantic = payload.get("semantic_artifact") if isinstance(payload.get("semantic_artifact"), dict) else None
    errors: list[str] = []
    warnings: list[str] = []
    definition = semantic_artifact_definition(current_state)
    if definition is not None and semantic is None:
        errors.append(f"{current_state} requires semantic_artifact metadata")
    if semantic is not None:
        required = ("path", "kind", "schema_name", "consumed_by", "writeback_policy")
        for field in required:
            if not str(semantic.get(field) or "").strip():
                errors.append(f"semantic_artifact.{field} is missing")
        semantic_path = str(semantic.get("path") or "").replace("\\", "/")
        if semantic_path not in expected:
            errors.append("semantic_artifact.path is not in expected_outputs")
        if definition is not None:
            scene_id = str(payload.get("scene_id") or "")
            expected_contract = semantic_artifact_contract(current_state, scene_id)
            if expected_contract is not None:
                for field in ("path", "schema_name", "consumed_by"):
                    if str(semantic.get(field) or "") != expected_contract[field]:
                        errors.append(f"semantic_artifact.{field} does not match authoritative contract")
        contracts = payload.get("output_contracts") if isinstance(payload.get("output_contracts"), list) else []
        matching = next((item for item in contracts if isinstance(item, dict) and str(item.get("path") or "").replace("\\", "/") == semantic_path), None)
        if matching is None:
            errors.append("semantic artifact has no output_contract entry")
        else:
            for field in ("kind", "schema_name", "consumed_by"):
                if str(matching.get(field) or "") != str(semantic.get(field) or ""):
                    errors.append(f"semantic output_contract.{field} does not match semantic_artifact")
    elif str(payload.get("execution_policy") or "") == "agent-required" and current_state.endswith("-agent-task"):
        warnings.append("agent task has no typed semantic artifact; verify that it is a pure decision marker rather than a creative/review task")

    if str(payload.get("execution_policy") or "") == "agent-required":
        owned = payload.get("system_owned_fields") if isinstance(payload.get("system_owned_fields"), dict) else {}
        lifecycle = owned.get("lifecycle") if isinstance(owned.get("lifecycle"), dict) else {}
        identity = lifecycle.get("task_identity") if isinstance(lifecycle.get("task_identity"), dict) else {}
        for field in ("task_id", "route", "current_state"):
            if str(identity.get(field) or "") != str(payload.get(field) or ""):
                errors.append(f"system_owned_fields.lifecycle.task_identity.{field} does not match task package")
        receipts = lifecycle.get("completion_receipts") if isinstance(lifecycle.get("completion_receipts"), list) else []
        receipt_by_path = {
            str(item.get("path") or "").replace("\\", "/"): item
            for item in receipts
            if isinstance(item, dict)
        }
        for marker in sorted(item for item in expected if item.endswith(".agent_completion.json")):
            receipt = receipt_by_path.get(marker)
            if receipt is None:
                errors.append(f"completion marker {marker} is missing from system_owned_fields.lifecycle")
                continue
            for field in ("schema", "source_task", "status"):
                if not str(receipt.get(field) or "").strip():
                    errors.append(f"completion receipt {marker} is missing {field}")
            if not isinstance(receipt.get("expected_artifacts_checked"), bool):
                errors.append(f"completion receipt {marker} has no boolean expected_artifacts_checked")
        if semantic is not None:
            semantic_owned = owned.get("semantic") if isinstance(owned.get("semantic"), dict) else {}
            for field in ("path", "schema_name", "scene_id", "consumed_by"):
                expected_value = str(semantic.get(field) or payload.get(field) or "")
                if str(semantic_owned.get(field) or "") != expected_value:
                    errors.append(f"system_owned_fields.semantic.{field} does not match semantic task contract")
    return {
        "task": _rel(path, root),
        "task_id": str(payload.get("task_id") or ""),
        "current_state": current_state,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def _render_markdown(payload: dict[str, Any], root: Path) -> str:
    summary = payload["summary"]
    lines = [
        "# Task Contract Audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Tasks: `{summary['task_count']}`",
        f"- Errors: `{summary['error_count']}`",
        "",
        "## Results",
        "",
    ]
    for task in payload["tasks"]:
        lines.append(f"### `{task.get('task_id') or task['task']}` - `{task['status']}`")
        lines.append("")
        for error in task["errors"]:
            lines.append(f"- Error: {error}")
        for warning in task["warnings"]:
            lines.append(f"- Warning: {warning}")
        if not task["errors"] and not task["warnings"]:
            lines.append("- Contract matches the authoritative semantic task definition.")
        lines.append("")
    return "\n".join(lines)


def _resolve(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
