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
from ..project_agent.archive_actions import archive_read_action
from ..project_agent.read_models import dependencies_from_read_models
from ..application.style.owner_directive import read_owner_style_directive, write_owner_style_directive
from ..application.style import StyleApplicationService
from ..application.lean_chapter_extension import extend_lean_chapter
from ..application.creator_persona import CreatorPersonaStore
from ..application.lean_future_replan import replan_lean_future
from ..application.lean_longform_planning import LeanLongformPlanningService
from ..application.lean_assets import ensure_lean_planning_assets, lean_asset_alignment
from ..application.lean_asset_enrichment import enrich_lean_planning_assets
from ..runtime.role_conversation import RoleConversationGateway
from ..project_manager import create_project, list_projects, record_direction
from literary_engineering_studio_engine.public.literary import (
    load_creative_quality_profile,
    load_rhythm_plan,
    save_creative_quality_profile,
    save_rhythm_plan,
    list_actor_personas,
    save_actor_persona,
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
    prompts: Any = None,
) -> ProjectAgentService:
    jobs, style_catalog = lifecycle.persistence.worker, StyleApplicationService()
    creator_personas = CreatorPersonaStore(Path(str(config.get("application", {}).get("data_root") or ".")))

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
            actor_personas=list_actor_personas,
            archive_read=archive_read_action(archive_dependencies),
            owner_style_read=read_owner_style_directive, style_versions=lambda root: style_catalog.version_catalog(project_root=root),
            style_version_detail=style_catalog.version_detail,
            creator_persona=lambda root, _arguments: creator_personas.read_current(root),
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
            extend_chapter=lambda root, **values: extend_lean_chapter(root, _role_gateway(config), **values),
            replan_future=lambda root, **values: replan_lean_future(root, _role_gateway(config), **values),
            save_actor_persona=save_actor_persona,
            archive_dependencies=archive_dependencies,
            write_owner_style=write_owner_style_directive,
            reconcile_assets=lambda root, **values: _reconcile_lean_assets(config, root, **values),
            prepare_plan=lambda root: _prepare_lean_plan(config, root),
            save_creator_persona=creator_personas.save,
        ),
        persona_loader=lambda root: active_persona(
            Path(str(config.get("application", {}).get("data_root") or ".")), root,
            prompt_resolver=(lambda layer_id, project: prompts.resolve(layer_id, project).text)
            if prompts is not None else None,
        ),
        prompt_resolver=(lambda layer_id, root: prompts.resolve(layer_id, root).text)
        if prompts is not None else None,
        goal_run_reader=lambda run_id: _goal_run_reader(jobs, run_id),
    )


def _role_gateway(config: dict[str, Any]) -> RoleConversationGateway:
    return RoleConversationGateway(
        config,
        data_root=Path(str(config.get("application", {}).get("data_root") or ".")) / "pi-conversations",
    )


def _prepare_lean_plan(config: dict[str, Any], root: Path) -> dict[str, Any]:
    data_root = Path(str(config.get("application", {}).get("data_root") or "."))
    return LeanLongformPlanningService(config, data_root=data_root).ensure_initial(root)


def _reconcile_lean_assets(
    config: dict[str, Any], root: Path, *, target_asset_id: str,
) -> dict[str, Any]:
    alignment = lean_asset_alignment(root)
    if not alignment["available"]:
        raise ValueError("lean planning assets are unavailable; use the formal asset route or owner archive creation")
    item = next((row for row in alignment["items"] if row["asset_id"] == target_asset_id), None)
    if item is None:
        raise ValueError("asset is not in the lean plan; use owner archive creation for a new asset")
    if item["status"] in {"identity_mismatch", "path_conflict"}:
        raise ValueError(
            f"planned asset identity needs author resolution: {item['status']} "
            f"({', '.join(item['matching_asset_ids'])})"
        )
    created = ensure_lean_planning_assets(root, target_asset_id=target_asset_id)
    enriched = enrich_lean_planning_assets(
        root, _role_gateway(config),
        target_asset_id=target_asset_id,
    )
    after = lean_asset_alignment(root)
    return {
        **created, **enriched,
        "alignment": next(row for row in after["items"] if row["asset_id"] == target_asset_id),
    }


def _goal_run_reader(jobs: Any, run_id: str) -> dict[str, Any]:
    run = dict(jobs.read_autopilot_run(run_id))
    checkpoint = jobs.latest_autopilot_event(run_id, "lean_scene.chapter-checkpoint")
    if isinstance(checkpoint, dict) and isinstance(checkpoint.get("data"), dict):
        run["chapter_update"] = dict(checkpoint["data"])
    run.update(_goal_event_evidence(jobs.autopilot_events_since(run_id, 0, limit=2000)))
    return run


def _goal_event_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "revision_summary": _revision_evidence(events),
        "scene_performance_summary": _performance_evidence(events),
    }


def _revision_evidence(events: list[dict[str, Any]]) -> dict[str, int]:
    attempts: dict[str, int] = {}
    for event in events:
        if event.get("event") != "worker.scene.revised":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        scene_id = str(data.get("scene_id") or "")
        if scene_id:
            attempts[scene_id] = max(attempts.get(scene_id, 0), int(data.get("revision_attempts") or 0))
    return {"total_attempts": sum(attempts.values()), "scene_count": len(attempts),
            "max_attempts": max(attempts.values(), default=0)}


def _performance_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    turns: dict[tuple[str, int], dict[str, Any]] = {}
    environments: dict[str, int] = {}
    committed: set[str] = set()
    for event in events:
        name = str(event.get("event") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        tx_id = str(data.get("scene_transaction_id") or data.get("transaction_id") or "")
        if name == "worker.scene.performance.interaction.turn" and tx_id:
            turns[(tx_id, int(data.get("turn") or 0))] = data
        elif name == "worker.scene.performance.environment" and tx_id:
            environments[tx_id] = max(environments.get(tx_id, 0), int(data.get("passages") or 0))
        elif name == "worker.scene.committed" and tx_id:
            committed.add(tx_id)
    return _committed_performance_summary(turns, environments, committed)


def _committed_performance_summary(
    turns: dict[tuple[str, int], dict[str, Any]], environments: dict[str, int], committed: set[str],
) -> dict[str, Any]:
    committed_turns = {key: value for key, value in turns.items() if key[0] in committed}
    scene_ids = {tx_id for tx_id, _ in committed_turns}
    return {
        "committed_interaction_scenes": len(scene_ids), "interaction_turns": len(committed_turns),
        "actor_entries": sum(int(value.get("entries") or 0) for value in committed_turns.values()),
        "speakers": sorted({str(value.get("speaker") or "") for value in committed_turns.values()
                            if value.get("speaker")}),
        "environment_passages": sum(environments.get(tx_id, 0) for tx_id in scene_ids),
    }


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
