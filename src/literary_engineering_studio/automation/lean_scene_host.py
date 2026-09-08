"""Autopilot host adapter for the lean scene-transaction coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import SceneExecutionMode

from .lean_scene_loop import LeanSceneRunCoordinator
from .policy import DelegationPolicy
from ..infrastructure.lean_scene_runtime import build_lean_scene_runtime
from ..observability.creative_live.scene_transactions import scene_transaction_summary
from ..runtime.runtime_selection import runtime_for_role


EventCallback = Callable[[str, str, dict[str, Any]], None]
PauseCallback = Callable[[str, str, str], None]


class _AutopilotSceneEvents:
    def __init__(self, emit: EventCallback, run_id: str):
        self._emit = emit
        self._run_id = run_id

    def emit(self, event: str, transaction: Any) -> None:
        summary = scene_transaction_summary(transaction)
        data = {**summary, "scene_transaction_id": transaction.transaction_id}
        self._emit(self._run_id, event, data)
        if transaction.creative_result is not None and event in {"scene.created", "scene.revised"}:
            self._emit_preview(transaction, data)
        if event == "scene.committed":
            self._emit_commit(transaction, data)

    def _emit_preview(self, transaction: Any, data: dict[str, Any]) -> None:
        prose = transaction.creative_result.prose
        self._emit(
            self._run_id,
            "artifact.preview.snapshot",
            {
                **data,
                "attempt_id": transaction.transaction_id,
                "path": f"drafts/scenes/{transaction.scene_id}.md",
                "kind": "prose",
                "format": "markdown",
                "identity": "streaming_preview",
                "content": prose,
                "characters": len(prose),
                "revision": transaction.version,
            },
        )

    def _emit_commit(self, transaction: Any, data: dict[str, Any]) -> None:
        self._emit(
            self._run_id,
            "writeback.approved",
            {
                **data,
                "attempt_id": transaction.transaction_id,
                "path": f"drafts/scenes/{transaction.scene_id}.md",
                "kind": "prose",
                "format": "markdown",
                "identity": "promoted",
                "characters": data["body_hanzi"],
                "revision": transaction.version,
            },
        )


class LeanSceneAutopilotHost:
    def __init__(
        self,
        *,
        config: dict[str, Any],
        runs: Any,
        scene_transactions: Any,
        execution_coordinator: Any,
        emit_event: EventCallback,
        pause: PauseCallback,
    ):
        self._config = config
        self._runs = runs
        self._scene_transactions = scene_transactions
        self._execution_coordinator = execution_coordinator
        self._emit_event = emit_event
        self._pause = pause
        self._coordinators: dict[str, LeanSceneRunCoordinator] = {}

    def shutdown(self) -> None:
        self._coordinators.clear()

    def coordinator(self, run_id: str, project: Path) -> LeanSceneRunCoordinator:
        existing = self._coordinators.get(run_id)
        if existing is not None:
            return existing
        if self._scene_transactions is None:
            raise RuntimeError("lean-v2 scene transaction persistence is unavailable")
        application = self._config.get("application")
        application = application if isinstance(application, dict) else {}
        data_root = Path(str(application.get("data_root") or ".")).expanduser().resolve()
        bundle = build_lean_scene_runtime(
            self._config,
            project_root=project,
            data_root=data_root,
            repository=self._scene_transactions,
            event_sink=lambda event, data: self._emit_event(run_id, event, data),
            transaction_events=_AutopilotSceneEvents(self._emit_event, run_id),
        )
        self._coordinators[run_id] = bundle.coordinator
        return bundle.coordinator

    def advance(
        self,
        run_id: str,
        project: Path,
        policy: DelegationPolicy,
        coordinator: LeanSceneRunCoordinator,
    ) -> bool:
        run = self._runs.read_autopilot_run(run_id)
        self._validate_runtime(run)
        owner = f"autopilot:{run_id}:lean-scene"
        if not self._acquire(project, owner):
            self._pause(run_id, "project-busy", "同一作品已有另一项正式任务正在执行，请稍后继续。")
            return True
        try:
            step = coordinator.advance_one(
                mode=SceneExecutionMode(policy.scene_execution_mode),
                steward_approved=policy.permits("scene-development", "canon_patch_approval"),
            )
        finally:
            self._release(project, owner)
        self._record_step(run_id, step)
        return self._apply_step(run_id, run, step)

    def _validate_runtime(self, run: dict[str, Any]) -> None:
        if str(run.get("runtime") or "") != "pi-worker":
            raise ValueError("lean-v2 scene transactions currently require the Pi Worker runtime")
        for role in ("worker", "reviewer"):
            if runtime_for_role(self._config, role) != "pi-worker":
                raise ValueError(f"lean-v2 requires agent_runtime_roles.{role}=pi-worker")

    def _acquire(self, project: Path, owner: str) -> bool:
        return self._execution_coordinator is None or self._execution_coordinator.acquire(project, owner)

    def _release(self, project: Path, owner: str) -> None:
        if self._execution_coordinator is not None:
            self._execution_coordinator.release(project, owner)

    def _record_step(self, run_id: str, step: Any) -> None:
        self._runs.append_autopilot_event(
            run_id,
            f"lean_scene.{step.action}",
            {
                "scene_id": step.scene_id,
                "transaction_id": step.transaction_id,
                "status": step.transaction_status,
                "message": step.message,
            },
        )

    def _apply_step(self, run_id: str, run: dict[str, Any], step: Any) -> bool:
        if step.route_ready:
            self._runs.update_autopilot_run(
                run_id,
                route_index=int(run.get("route_index") or 0) + 1,
                current_task_id="",
            )
            return False
        if step.waiting_human:
            self._pause(run_id, "lean-scene-approval-required", step.message)
            return True
        if step.blocked:
            self._pause(run_id, "lean-scene-checkpoint", step.message)
            return True
        task_id = self._task_id(step)
        if step.committed:
            self._runs.advance_autopilot_run(
                run_id,
                current_route="scene-development",
                current_task_id=task_id,
                last_error="",
                consecutive_revisions=0,
            )
        else:
            self._runs.update_autopilot_run(
                run_id,
                current_route="scene-development",
                current_task_id=task_id,
                last_error="",
            )
        return False

    @staticmethod
    def _task_id(step: Any) -> str:
        if step.scene_id:
            return f"lean-scene:{step.scene_id}:{step.transaction_status}"
        return f"lean-scene:{step.action}"


__all__ = ["LeanSceneAutopilotHost"]
