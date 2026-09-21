"""Bridge legacy run indexes to lightweight, task-free literary operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import ensure_default_style_mount

from ..application.lean_book_audit import audit_lean_book
from ..application.lean_assets import ensure_lean_planning_assets
from ..application.lean_source_context import imported_source_context
from ..application.lean_longform_planning import LeanLongformPlanningService
from ..runtime.runtime_selection import runtime_for_role
from .run_result_contracts import RouteCycle


class LeanRouteAutopilotHost:
    def __init__(
        self,
        *,
        config: dict[str, Any],
        runs: Any,
        execution_coordinator: Any,
        emit_event: Callable[[str, str, dict[str, Any]], None],
        pause: Callable[[str, str, str], None],
    ) -> None:
        self.config = config
        self.runs = runs
        self.execution_coordinator = execution_coordinator
        self.emit_event = emit_event
        self.pause = pause
        application = config.get("application")
        application = application if isinstance(application, dict) else {}
        self.data_root = Path(str(application.get("data_root") or ".")).expanduser().resolve()

    def advance(self, run_id: str, project: Path, cycle: RouteCycle) -> bool:
        owner = f"autopilot:{run_id}:lean-route"
        if self.execution_coordinator is not None and not self.execution_coordinator.acquire(project, owner):
            self.pause(run_id, "project-busy", "同一作品已有另一项正式任务正在执行，请稍后继续。")
            return True
        try:
            data = self._execute(run_id, project, cycle.route)
        finally:
            if self.execution_coordinator is not None:
                self.execution_coordinator.release(project, owner)
        self.emit_event(run_id, "lean_route.completed", {"route": cycle.route, **data})
        if cycle.route in {"longform-planning", "review-and-audit"}:
            self.runs.advance_autopilot_run(
                run_id, route_index=cycle.route_index + 1, current_task_id="", last_error="",
            )
        else:
            self.runs.update_autopilot_run(
                run_id, route_index=cycle.route_index + 1, current_task_id="", last_error="",
            )
        return False

    def _execute(self, run_id: str, project: Path, route: str) -> dict[str, Any]:
        if route == "source-ingest":
            count, _ = imported_source_context(project)
            return {"mode": "source-evidence" if count else "no-imports", "import_count": count}
        if route == "longform-planning":
            run = self.runs.read_autopilot_run(run_id)
            if str(run.get("runtime") or "") != "pi-worker" or runtime_for_role(self.config, "worker") != "pi-worker":
                raise ValueError("lean-v2 planning requires the Pi Worker runtime")
            ensure_default_style_mount(project)
            plan = LeanLongformPlanningService(
                self.config,
                data_root=self.data_root,
                event_sink=lambda event, data: self.emit_event(run_id, event, data),
            ).ensure_initial(project)
            return {"chapter_count": len(plan["chapters"]), "planned_scenes": len(plan["scenes"])}
        if route == "style-engineering":
            ensure_default_style_mount(project)
            return {"mode": "mounted-style"}
        if route == "character-and-world-assets":
            return ensure_lean_planning_assets(project)
        if route == "review-and-audit":
            audit = audit_lean_book(project, self.data_root)
            return {"chapter_count": audit["chapter_count"], "scene_count": audit["scene_count"]}
        if route == "export-and-release":
            return {"mode": "release-next"}
        raise ValueError(f"unsupported lean literary route: {route}")


__all__ = ["LeanRouteAutopilotHost"]
