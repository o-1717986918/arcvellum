"""Serial production executor for whitelisted adaptive-plan bundles.

The executor owns no task lifecycle.  It validates the next formal
``TaskPackage`` and delegates every actual step to the existing AgentWorker.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from ..contracts import TaskPackage
from ..orchestration.bundles import (
    ExecutionBundle,
    bundle_violations,
    compile_bundles,
)
from .worker_paths import validate_project
from .worker_results import WorkerRunResult


@dataclass(frozen=True)
class BundleExecutionOutcome:
    status: str
    completed_task_ids: tuple[str, ...]
    final_result: WorkerRunResult | None
    reason: str = ""


@dataclass(frozen=True)
class BundleDispatchPlan:
    project: Path
    first_task: TaskPackage
    bundle: ExecutionBundle


class SerialBundleExecutor:
    """Run formal tasks in order until the bundle reaches a hard boundary."""

    def __init__(self, *, max_formal_steps: int = 32):
        if max_formal_steps < 1:
            raise ValueError("max_formal_steps must be positive")
        self.max_formal_steps = max_formal_steps

    def execute(
        self,
        bundle: ExecutionBundle,
        *,
        next_task: Callable[[], TaskPackage | None],
        run_task: Callable[[TaskPackage], WorkerRunResult],
    ) -> BundleExecutionOutcome:
        violations = bundle_violations(bundle)
        if violations:
            return BundleExecutionOutcome(
                status="invalid_bundle",
                completed_task_ids=(),
                final_result=None,
                reason="; ".join(item.message for item in violations),
            )

        completed: list[str] = []
        seen: set[str] = set()
        final: WorkerRunResult | None = None
        for _ in range(self.max_formal_steps):
            task = next_task()
            if task is None:
                return BundleExecutionOutcome(
                    status="route_ready",
                    completed_task_ids=tuple(completed),
                    final_result=final,
                )
            identity_error = _task_identity_error(bundle, task)
            if identity_error == "stop_before":
                return BundleExecutionOutcome(
                    status="stopped_before",
                    completed_task_ids=tuple(completed),
                    final_result=final,
                )
            if identity_error:
                return BundleExecutionOutcome(
                    status="fixed_fallback",
                    completed_task_ids=tuple(completed),
                    final_result=final,
                    reason=identity_error,
                )
            if task.task_id in seen:
                return BundleExecutionOutcome(
                    status="no_progress",
                    completed_task_ids=tuple(completed),
                    final_result=final,
                    reason=f"formal task repeated without progress: {task.task_id}",
                )
            seen.add(task.task_id)
            final = run_task(task)
            if final.status != "complete":
                return BundleExecutionOutcome(
                    status="task_terminal",
                    completed_task_ids=tuple(completed),
                    final_result=final,
                    reason=final.message,
                )
            completed.append(task.task_id)

        return BundleExecutionOutcome(
            status="step_limit",
            completed_task_ids=tuple(completed),
            final_result=final,
            reason="bundle exceeded the bounded formal-step limit",
        )


class BundleDispatchHost(Protocol):
    observer: Any

    def _select_task_package(
        self,
        project: Path,
        *,
        route: str,
        task_id: str = "",
        scene: str = "",
        emit_binding_events: bool,
    ) -> tuple[TaskPackage | None, str]: ...

    def _active_scene_plan(self, project_root: Path): ...

    def run_once(
        self,
        project_root: Path,
        *,
        route: str,
        runtime_id: str,
        task_id: str = "",
        scene: str = "",
    ) -> WorkerRunResult: ...


def dispatch_serial_bundle(
    host: BundleDispatchHost,
    project_root: Path,
    *,
    route: str,
    runtime_id: str,
    scene: str,
) -> WorkerRunResult | None:
    """Bind one current formal task to a bundle and execute it safely."""

    project = validate_project(project_root)
    selected = _select_dispatch_plan(
        host,
        project,
        route=route,
        runtime_id=runtime_id,
        scene=scene,
    )
    if selected is None or isinstance(selected, WorkerRunResult):
        return selected
    host.observer.emit(
        "orchestration.bundle.started",
        {
            "bundle_id": selected.bundle.bundle_id,
            "template_id": selected.bundle.template_id,
            "scope_key": selected.bundle.scope_key,
        },
    )
    outcome = _execute_dispatch_plan(
        host,
        selected,
        route=route,
        runtime_id=runtime_id,
        scene=scene,
    )
    return _finish_dispatch(host, selected.bundle, outcome)


def _select_dispatch_plan(
    host: BundleDispatchHost,
    project: Path,
    *,
    route: str,
    runtime_id: str,
    scene: str,
) -> BundleDispatchPlan | WorkerRunResult | None:
    try:
        first, ready_message = host._select_task_package(
            project,
            route=route,
            scene=scene,
            emit_binding_events=False,
        )
        if first is None:
            return WorkerRunResult(
                "route_ready",
                project,
                route,
                "",
                runtime_id,
                None,
                None,
                ready_message or "route has no pending task",
                audit_fields={
                    "status": "route-ready",
                    "scope": "bundle-terminal-scan",
                },
            )
        node_id = str(first.payload.get("creative_plan_node_id") or "")
        scope_key = str(first.payload.get("scene_id") or "")
        if not node_id or not scope_key:
            return None
        active = host._active_scene_plan(project)
        if active is None:
            return None
        context_hash = str(
            first.payload.get("creative_chapter_policy_digest")
            or active.project_fingerprint
        )
        bundles = compile_bundles(
            active.graph,
            scope_key=scope_key,
            context_snapshot_hash=context_hash,
        )
        bundle = next(
            (item for item in bundles if node_id in item.step_node_ids),
            None,
        )
        if bundle is None:
            return None
        return BundleDispatchPlan(project, first, bundle)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        host.observer.emit(
            "orchestration.fixed_fallback",
            {"reason": f"bundle-selection-failed: {exc}"},
        )
        return None


def _execute_dispatch_plan(
    host: BundleDispatchHost,
    plan: BundleDispatchPlan,
    *,
    route: str,
    runtime_id: str,
    scene: str,
) -> BundleExecutionOutcome:
    pending = [plan.first_task]

    def next_task() -> TaskPackage | None:
        if pending:
            return pending.pop()
        task, _ = host._select_task_package(
            plan.project,
            route=route,
            scene=scene,
            emit_binding_events=False,
        )
        return task

    return SerialBundleExecutor().execute(
        plan.bundle,
        next_task=next_task,
        run_task=lambda task: host.run_once(
            plan.project,
            route=route,
            runtime_id=runtime_id,
            task_id=task.task_id,
            scene=scene,
        ),
    )


def _finish_dispatch(
    host: BundleDispatchHost,
    bundle: ExecutionBundle,
    outcome: BundleExecutionOutcome,
) -> WorkerRunResult | None:
    host.observer.emit(
        "orchestration.bundle.finished",
        {
            "bundle_id": bundle.bundle_id,
            "status": outcome.status,
            "completed_task_ids": list(outcome.completed_task_ids),
            "reason": outcome.reason,
        },
    )
    if outcome.status in {
        "invalid_bundle",
        "fixed_fallback",
        "no_progress",
        "step_limit",
    }:
        host.observer.emit(
            "orchestration.fixed_fallback",
            {"reason": outcome.reason or outcome.status},
        )
    if outcome.final_result is None:
        return None
    audit = dict(outcome.final_result.audit_fields or {})
    audit.update(
        {
            "bundle_id": bundle.bundle_id,
            "bundle_status": outcome.status,
            "bundle_steps": str(len(outcome.completed_task_ids)),
        }
    )
    return replace(outcome.final_result, audit_fields=audit)


def _task_identity_error(bundle: ExecutionBundle, task: TaskPackage) -> str:
    payload = task.payload
    if str(payload.get("creative_plan_id") or "") != bundle.plan_id:
        return "formal task belongs to another active plan"
    if str(payload.get("creative_plan_node_kind") or "") in bundle.stop_before:
        return "stop_before"
    node_id = str(payload.get("creative_plan_node_id") or "")
    if node_id not in bundle.step_node_ids:
        return f"formal task node is outside bundle: {node_id or 'unbound'}"
    if str(payload.get("creative_plan_agent_role") or "") != bundle.agent_role:
        return "formal task Agent role does not match bundle role"
    if str(payload.get("scene_id") or payload.get("chapter_id") or "") != bundle.scope_key:
        return "formal task scope does not match bundle scope"
    return ""
