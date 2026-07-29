"""Build the immutable metadata projection for one staged Worker run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import TaskPackage
from .creative_plan_context import creative_plan_task_context
from .task_snapshot import TaskSnapshot


RUN_MANIFEST_SCHEMA = "literary-engineering-studio/task-sandbox/v0.1"


def build_run_manifest_payload(
    *,
    task: TaskPackage,
    run_id: str,
    runtime: str,
    created_at: str,
    workspace: Path,
    control_workspace: Path,
    prompt_path: Path,
    copied_sources: list[str],
    missing_sources: list[str],
    reference_paths: tuple[str, ...],
    task_snapshot: TaskSnapshot,
    execution_fields: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": RUN_MANIFEST_SCHEMA,
        "run_id": run_id,
        "status": "prepared",
        "created_at": created_at,
        "runtime": runtime,
        "project_root": str(task.project_root),
        "task_id": task.task_id,
        "task_json": str(task.task_json_path),
        "task_markdown": str(task.task_markdown_path),
        "route": task.route,
        "current_state": task.current_state,
        "workspace": str(workspace),
        "control_workspace": str(control_workspace),
        "prompt": str(prompt_path),
        "copied_sources": copied_sources,
        "reference_paths": list(reference_paths),
        "omitted_reference_paths": [
            path for path in task.required_reading if path not in reference_paths
        ],
        "missing_sources": missing_sources,
        "expected_outputs": list(task.expected_outputs),
        "human_gate_reasons": list(task.human_gate_reasons),
        "execution_contract": task.execution_contract.as_dict(),
        "task_snapshot": task_snapshot.manifest_projection(workspace.parent),
        "creative_plan": creative_plan_task_context(task.payload),
        **execution_fields,
    }
