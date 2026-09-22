"""Compose the Project Agent from existing application services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import WorkerRequest
from .routers.project_agent import ProjectAgentRouterDependencies, build_project_agent_router
from .streaming import numeric_resume_cursor, sse, stream_terminal
from .routers.worker import launch_worker
from ..advisor_personas import active_persona
from ..core_read_models import current_choices, record_choice
from ..project_agent import ProjectAgentService
from ..project_agent.actions import dependencies_from_actions
from ..project_agent.read_models import dependencies_from_read_models
from ..application.lean_chapter_extension import extend_lean_chapter
from ..runtime.role_conversation import RoleConversationGateway
from ..project_manager import create_project, list_projects, record_direction
from literary_engineering_studio_engine.public.literary import (
    load_creative_quality_profile,
    load_rhythm_plan,
    save_creative_quality_profile,
    save_rhythm_plan,
)


def build_project_agent_service(
    config: dict[str, Any],
    *,
    lifecycle: Any,
    autopilot: Any,
    style_mounts: Any,
    read_models: Any,
    archive_dependencies: Any,
    worker_dependencies: Any,
) -> ProjectAgentService:
    jobs = lifecycle.persistence.worker

    def goal_run_reader(run_id: str) -> dict[str, Any]:
        run = dict(jobs.read_autopilot_run(run_id))
        checkpoint = jobs.latest_autopilot_event(run_id, "lean_scene.chapter-checkpoint")
        if isinstance(checkpoint, dict) and isinstance(checkpoint.get("data"), dict):
            run["chapter_update"] = dict(checkpoint["data"])
        attempts: dict[str, int] = {}
        for event in jobs.autopilot_events_since(run_id, 0, limit=2000):
            if str(event.get("event") or "") != "scene.revised":
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            scene_id = str(data.get("scene_id") or "")
            if scene_id:
                attempts[scene_id] = max(attempts.get(scene_id, 0), int(data.get("revision_attempts") or 0))
        run["revision_summary"] = {
            "total_attempts": sum(attempts.values()),
            "scene_count": len(attempts),
            "max_attempts": max(attempts.values(), default=0),
        }
        return run

    return ProjectAgentService(
        config,
        sessions=lifecycle.persistence.sessions,
        jobs=lifecycle.persistence.worker,
        dependencies=dependencies_from_read_models(
            read_models,
            choices=lambda root: current_choices(
                config, root, dashboard=read_models.dashboard(root).get("dashboard")
            ),
            quality=load_creative_quality_profile,
            rhythm=load_rhythm_plan,
            style_mounts=style_mounts.status,
            archive_candidates=archive_dependencies.candidates.list,
            project_catalog=list_projects,
        ),
        actions=dependencies_from_actions(
            record_direction=record_direction,
            autopilot=autopilot,
            config=config,
            current_choices=lambda settings, root: current_choices(
                settings, root, dashboard=read_models.dashboard(root).get("dashboard")
            ),
            record_choice=lambda settings, root, payload: record_choice(
                settings, root, payload, style_mount_service=style_mounts
            ),
            save_quality=save_creative_quality_profile,
            save_rhythm=save_rhythm_plan,
            load_rhythm=load_rhythm_plan,
            style_mounts=style_mounts,
            candidate_promotions=archive_dependencies.candidates,
            launch_worker=lambda request: launch_worker(
                worker_dependencies, WorkerRequest(**request)
            ),
            invalidate_project=read_models.invalidate,
            create_project=lambda **values: create_project(
                parent_directory=str(config.get("application", {}).get("projects_root") or ""),
                **values,
            ),
            goal_evidence=lambda root: read_models.reader(root),
            extend_chapter=lambda root, **values: extend_lean_chapter(
                root,
                RoleConversationGateway(
                    config,
                    data_root=Path(str(config.get("application", {}).get("data_root") or ".")) / "pi-conversations",
                ),
                **values,
            ),
        ),
        persona_loader=lambda root: active_persona(
            Path(str(config.get("application", {}).get("data_root") or ".")), root
        ),
        goal_run_reader=goal_run_reader,
    )


def register_project_agent_router(app: Any, service: ProjectAgentService, jobs: Any) -> None:
    app.include_router(
        build_project_agent_router(
            ProjectAgentRouterDependencies(
                service=service,
                jobs=jobs,
                sse=sse,
                numeric_resume_cursor=numeric_resume_cursor,
                stream_terminal=stream_terminal,
            )
        )
    )


__all__ = ["build_project_agent_service", "register_project_agent_router"]
