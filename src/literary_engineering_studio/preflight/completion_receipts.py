"""Deterministic lifecycle receipts for completed Agent tasks."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest


LEGACY_AGENT_STATES = {
    "roleplay-agent-task",
    "branch-agent-task",
    "branch-selection",
    "composition-agent-task",
    "state-agent-task",
    "canon-agent-task",
    "continuity-ledger-agent-task",
    "continuity-ledger-review",
}


def canonicalize_agent_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    read_object: Callable[[Path], dict[str, Any] | None],
) -> list[dict[str, str]]:
    """Write receipts only after every substantive expected output exists."""

    if not _requires_agent_receipt(task) or task.route == "character-and-world-assets":
        return []
    markers = [item for item in task.expected_outputs if item.endswith(".agent_completion.json")]
    non_markers = [item for item in task.expected_outputs if not item.endswith(".agent_completion.json")]
    if not markers or not _outputs_are_ready(sandbox, non_markers):
        return []
    contracts = _receipt_contracts(task)
    changes: list[dict[str, str]] = []
    for relative in markers:
        contract = contracts.get(relative.replace("\\", "/"), {})
        payload = _receipt_payload(relative, contract)
        if _write_if_changed(sandbox, relative, payload, read_object):
            changes.append(
                {
                    "path": relative,
                    "field": "completion",
                    "reason": "generated deterministic Agent-task completion metadata",
                }
            )
    return changes


def _requires_agent_receipt(task: TaskPackage) -> bool:
    task_type = str(task.payload.get("task_type") or "")
    return (
        str(task.payload.get("execution_policy") or "") == "agent-required"
        or task_type.startswith(("platform-agent", "main-platform-agent"))
        or task.current_state in LEGACY_AGENT_STATES
    )


def _outputs_are_ready(sandbox: SandboxManifest, outputs: list[str]) -> bool:
    return bool(outputs) and all(
        (sandbox.workspace / Path(item)).is_file()
        and (sandbox.workspace / Path(item)).stat().st_size > 0
        for item in outputs
    )


def _receipt_contracts(task: TaskPackage) -> dict[str, dict[str, object]]:
    owned = task.payload.get("system_owned_fields") if isinstance(task.payload.get("system_owned_fields"), dict) else {}
    lifecycle = owned.get("lifecycle") if isinstance(owned.get("lifecycle"), dict) else {}
    receipts = lifecycle.get("completion_receipts") if isinstance(lifecycle.get("completion_receipts"), list) else []
    return {
        str(item.get("path") or "").replace("\\", "/"): item
        for item in receipts
        if isinstance(item, dict)
    }


def _receipt_payload(relative: str, contract: dict[str, object]) -> dict[str, object]:
    base = relative[: -len(".agent_completion.json")]
    source_task = str(
        contract.get("source_task")
        or base + (".md" if base.endswith(".agent_tasks") else ".agent_tasks.md")
    )
    status = str(contract.get("status") or "complete")
    return {
        "schema": str(contract.get("schema") or "literary-engineering-workbench/agent-task-completion/v1"),
        "source_task": source_task,
        "status": status,
        "handled_by": "studio-worker",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "expected_artifacts_checked": bool(contract.get("expected_artifacts_checked", status == "complete")),
        "notes": ["Machine-owned completion receipt; route gates validate the Agent-authored result separately."],
    }


def _write_if_changed(
    sandbox: SandboxManifest,
    relative: str,
    payload: dict[str, object],
    read_object: Callable[[Path], dict[str, Any] | None],
) -> bool:
    path = sandbox.workspace / Path(relative)
    existing = read_object(path)
    comparable = dict(payload)
    comparable.pop("completed_at")
    existing_comparable = dict(existing or {})
    existing_comparable.pop("completed_at", None)
    source_task_path = sandbox.workspace / Path(str(payload["source_task"]))
    receipt_is_fresh = path.is_file() and (
        not source_task_path.is_file()
        or path.stat().st_mtime_ns >= source_task_path.stat().st_mtime_ns
    )
    if existing_comparable == comparable and receipt_is_fresh:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
