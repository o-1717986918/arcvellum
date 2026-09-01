"""Machine-owned metadata normalization for formal style tasks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from literary_engineering_studio_engine.public.literary import (
    style_review_machine_values,
)


STYLE_AGENT_STATES = {
    "style-prompt-agent-task",
    "style-prompt-quality",
    "style-eval-agent-task",
    "style-eval-revision",
    "style-review-agent-task",
}


def canonicalize_style_machine_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
) -> list[dict[str, str]]:
    state = str(task.current_state or "")
    if state not in STYLE_AGENT_STATES:
        return []
    profile_dir = str(task.payload.get("profile_dir") or "").replace("\\", "/").strip()
    if not profile_dir:
        return []
    changes: list[dict[str, str]] = []
    # A canonicalizer may only rewrite artifacts owned by the active task.
    # During style-eval-agent-task the prompt manifest is read-only evidence;
    # touching it here creates an unexpected sandbox change after restoration.
    if state in {"style-prompt-agent-task", "style-prompt-quality", "style-eval-revision"}:
        changes.extend(_canonicalize_prompt(task, sandbox, profile_dir))
    if state in {"style-eval-agent-task", "style-eval-revision"}:
        changes.extend(_canonicalize_evaluation(task, sandbox, profile_dir))
    if state == "style-review-agent-task":
        changes.extend(_canonicalize_review(task, sandbox, profile_dir))
    return changes


def _canonicalize_prompt(
    task: TaskPackage,
    sandbox: SandboxManifest,
    profile_dir: str,
) -> list[dict[str, str]]:
    relative = f"{profile_dir}/style_prompt.agent.json"
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    return _write_machine_fields(
        path,
        relative,
        payload,
        {
            "schema": "literary-engineering-workbench/style-prompt-agent/v1",
            "source_paths": [str(item).replace("\\", "/") for item in task.source_paths],
            "writer_session_id": _session_identity(task, "writer"),
        },
        "style-prompt",
    )


def _canonicalize_evaluation(
    task: TaskPackage,
    sandbox: SandboxManifest,
    profile_dir: str,
) -> list[dict[str, str]]:
    relative = f"{profile_dir}/evaluation_results/formal/platform_agent_candidate.prompt.json"
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    candidate = f"{profile_dir}/evaluation_results/formal/platform_agent_candidate.md"
    reference = next(
        (
            str(item).replace("\\", "/")
            for item in task.source_paths
            if str(item).lower().endswith(".txt")
        ),
        "",
    )
    expected = {
        "mode": "blind-review",
        "style_prompt": f"{profile_dir}/style_prompt.md",
        "reference": reference,
        "input": "project.yaml",
        "candidate": candidate,
        "style_prompt_sha256": _sha256(sandbox.workspace / f"{profile_dir}/style_prompt.md"),
        "reference_sha256": _sha256(sandbox.workspace / reference),
        "input_sha256": _sha256(sandbox.workspace / "project.yaml"),
        "candidate_sha256": _sha256(sandbox.workspace / candidate),
        "writer_session_id": _session_identity(task, "writer"),
    }
    return _write_machine_fields(path, relative, payload, expected, "style-evaluation")


def _canonicalize_review(
    task: TaskPackage,
    sandbox: SandboxManifest,
    profile_dir: str,
) -> list[dict[str, str]]:
    relative = f"{profile_dir}/evaluation_results/formal/style_semantic_review.json"
    path = sandbox.workspace / relative
    payload = _read_object(path)
    if payload is None:
        return []
    expected = style_review_machine_values(
        sandbox.workspace,
        sandbox.workspace / profile_dir,
        target_id=str(task.payload.get("target_id") or task.payload.get("profile_id") or ""),
        reviewer_session_id=_session_identity(task, "reviewer"),
    )
    if str(payload.get("status") or "").strip().lower() in {
        "completed",
        "done",
        "pending",
        "pending_agent_judgment",
        "reviewed",
    }:
        expected["status"] = "complete"
    return _write_machine_fields(path, relative, payload, expected, "style-review")


def _session_identity(task: TaskPackage, role: str) -> str:
    return f"studio:{role}:{task.task_id}"


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_machine_fields(
    path: Path,
    relative: str,
    payload: dict[str, Any],
    expected: dict[str, Any],
    reason: str,
) -> list[dict[str, str]]:
    changed: list[str] = []
    for field, value in expected.items():
        if not value or payload.get(field) == value:
            continue
        payload[field] = value
        changed.append(field)
    if not changed:
        return []
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [
        {
            "path": relative,
            "field": field,
            "reason": f"normalized deterministic {reason} metadata",
        }
        for field in changed
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
