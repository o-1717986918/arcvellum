"""Drive benchmark projects to a real Agent task through authoritative routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import TaskPackage, load_task_package
from ..runtime.worker import AgentWorker
from .runtime_benchmark_scene import (
    complete_synthetic_scene_task,
    supports_synthetic_completion,
)
from literary_engineering_studio_engine.tasking.registry import issue_next_task


def drive_benchmark_preparation(
    project: Path,
    *,
    route: str,
    expected_state: str,
    preparation: str,
    config: dict[str, Any],
) -> tuple[TaskPackage, int, int]:
    """Return the real target task and counts for all prerequisite closures."""

    worker = AgentWorker(config)
    deterministic_steps = 0
    synthetic_agent_steps = 0
    for _step in range(20):
        issued = issue_next_task(project, route=route)
        if issued.status != "issued" or not issued.task_id:
            raise RuntimeError(
                f"benchmark route became {issued.status} before {expected_state}: {route}"
            )
        task = load_task_package(
            project,
            project / "workflow" / "tasks" / f"{issued.task_id}.task.json",
        )
        if task.current_state == expected_state:
            if task.execution_contract.execution_policy != "agent-required":
                raise RuntimeError(f"benchmark target is not an Agent task: {task.current_state}")
            return task, deterministic_steps, synthetic_agent_steps
        if task.execution_contract.execution_policy == "agent-required":
            if preparation == "synthetic-scene-closure" and supports_synthetic_completion(task):
                complete_synthetic_scene_task(project, task, bridge=worker.bridge)
                synthetic_agent_steps += 1
                continue
            raise RuntimeError(
                "benchmark preparation reached an unexpected Agent task: "
                f"{task.current_state}"
            )
        result = worker.run_once(
            project,
            route=route,
            runtime_id="opencode",
            task_id=task.task_id,
        )
        if result.status != "complete":
            raise RuntimeError(
                f"benchmark deterministic prefix failed at {task.current_state}: {result.message}"
            )
        deterministic_steps += 1
    raise RuntimeError(f"benchmark preparation exceeded 20 steps: {route}/{expected_state}")
