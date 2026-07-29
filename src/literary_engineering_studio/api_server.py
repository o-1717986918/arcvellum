"""Local Studio API: reused core read models plus Agent Worker execution."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import threading
import time
from typing import Any, Callable

from . import __version__
from .application_info import build_application_info, build_diagnostic_report, build_legal_documents, export_diagnostic_report
from .application.style import StyleMountApplicationService
from .api.dependencies import archaeology_router_dependencies, style_lab_dependencies
from .api.common import call_handler as _call, friendly_error as _friendly_error, frontend_file as _frontend_file, project_root as _project
from .api.models import (
    ArchiveAssetArchiveRequest,
    ArchiveAssetCommitRequest,
    ArchiveAssetContentRequest,
    ArchiveAssetRestoreRequest,
    ArchiveCandidatePromotionRequest,
    ArchiveRestorePreviewRequest,
    AdvisorCustomPersonaRequest,
    AdvisorInboxReadRequest,
    AdvisorInboxSettingsRequest,
    AdvisorPersonaSelectionRequest,
    AdvisorQuestionRequest,
    AdvisorSessionRequest,
    AutopilotControlRequest,
    AutopilotPolicyRequest,
    AutopilotStartRequest,
    CreativeQualityPreviewRequest,
    CreativeQualityRequest,
    DirectionRequest,
    ModelSelectionRequest,
    OpenCodeCredentialRequest,
    ProjectCreateRequest,
    ProjectLocationRequest,
    ProjectOpenRequest,
    ProjectsRootRequest,
    ReaderBookmarkRequest,
    ReaderPositionRequest,
    RhythmPlanRequest,
    RunnerProbeRequest,
    StyleMountRequest,
    WorkerRequest,
    WorkerRetryRequest,
    WritebackDecisionRequest,
)
from .api.streaming import sse as _sse, stream_read_model as _stream_read_model, visible_delta_chunks as _visible_delta_chunks
from .api.routers.application import ApplicationRouterDependencies, build_application_router
from .api.routers.archive import build_archive_router, default_archive_dependencies
from .api.routers.archaeology import build_archaeology_router
from .api.routers.runners import RunnerRouterDependencies, build_runner_router
from .api.routers.projects import ProjectRouterDependencies, build_project_router
from .api.routers.quality import QualityRouterDependencies, build_quality_router
from .api.routers.advisor import AdvisorRouterDependencies, build_advisor_router
from .api.routers.automation import AutomationRouterDependencies, build_automation_router
from .api.routers.workflow import WorkflowRouterDependencies, build_workflow_router
from .api.routers.library import LibraryRouterDependencies, build_library_router
from .api.routers.narrative import NarrativeRouterDependencies, build_narrative_router
from .api.routers.delivery import DeliveryRouterDependencies, build_delivery_router
from .api.routers.style_lab import build_style_lab_router
from .api.routers.project_details import ProjectDetailRouterDependencies, build_project_detail_router
from .api.routers.worker import WorkerRouterDependencies, build_worker_router, launch_worker
from .advisor import ProjectAdvisor
from .agent_observability import build_agent_observability
from .api_read_models import ProjectReadModels
from .agent_session_tracking import track_agent_session_event
from .advisor_inbox import refresh_advisor_inbox, save_inbox_settings
from .advisor_personas import persona_catalog, save_custom_persona, select_persona
from .autopilot import AutopilotService
from .bootstrap import ApplicationBootstrapService
from .config import default_projects_root, load_config, save_config
from .core_bridge import CoreBridge
from .core_read_models import build_activity, build_dashboard, build_library, build_task_summary, current_choices
from .core_read_models import record_choice, record_ui_note, save_display_field
from .delivery import build_delivery, delivery_content_type, resolve_delivery_file
from .lifecycle import ApplicationLifecycleManager
from .live_events import EPHEMERAL_WORKER_EVENTS, coalesce_live_events
from .model_connections import model_connection_status
from .narrative_projection import build_narrative_projection, projection_delta, projection_motion_events
from .narrative_projection_v3 import (
    build_narrative_node_detail_v3,
    build_narrative_projection_v3,
    build_spatial_projection_patch,
    spatial_projection_delta,
    spatial_projection_motion_events,
)
from .project_progress import build_project_progress
from .opencode_binary import install_pinned_opencode, locate_opencode, verify_opencode
from .opencode_control import (
    connect_custom_provider,
    disconnect_provider,
    provider_catalog,
    select_model,
    set_api_credential,
)
from .runner_probe import probe_agent_runner
from .project_manager import (
    create_project,
    current_project,
    list_projects,
    read_directions,
    record_direction,
    register_project,
    validate_project_location,
)
from .reader import build_reader_manifest, public_reader_manifest, read_reader_unit, search_reader
from .supervisor import project_lock_key
from .worker import AgentWorker
from literary_engineering_studio_engine.anti_ai_style import style_lint_gate
from literary_engineering_studio_engine.creative_quality import (
    load_creative_quality_profile,
    save_creative_quality_profile,
)
from literary_engineering_studio_engine.punctuation_standard import lint_punctuation
from literary_engineering_studio_engine.rhythm_plan import load_rhythm_plan, save_rhythm_plan

_STYLE_MOUNTS = StyleMountApplicationService()

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
except ImportError:  # pragma: no cover
    FastAPI = None
    CORSMiddleware = None
    HTTPException = None
    HTMLResponse = None
    FileResponse = None
    Response = None
    StreamingResponse = None
    JSONResponse = None
    Request = None


def _narrative_dependencies(
    config: dict[str, Any],
    cached_read_model: Callable[..., dict[str, Any]],
    dashboard_snapshot: Callable[[Path], dict[str, Any]],
    narrative_evidence_snapshot: Callable[[Path], dict[str, Any]],
    v2_stream_state: dict[str, dict[str, Any]],
    v3_stream_state: dict[str, dict[str, Any]],
    stream_lock: threading.Lock,
) -> NarrativeRouterDependencies:
    return NarrativeRouterDependencies(
        config=config,
        cached_read_model=cached_read_model,
        dashboard_snapshot=dashboard_snapshot,
        narrative_evidence_snapshot=narrative_evidence_snapshot,
        build_projection=build_narrative_projection,
        projection_delta=projection_delta,
        projection_motion_events=projection_motion_events,
        build_projection_v3=build_narrative_projection_v3,
        build_node_detail_v3=build_narrative_node_detail_v3,
        spatial_projection_delta=spatial_projection_delta,
        spatial_projection_motion_events=spatial_projection_motion_events,
        spatial_projection_patch=build_spatial_projection_patch,
        v2_stream_state=v2_stream_state,
        v3_stream_state=v3_stream_state,
        stream_lock=stream_lock,
        sse=_sse,
    )


def _worker_dependencies(config: dict[str, Any], jobs: Any, lifecycle: Any) -> WorkerRouterDependencies:
    def worker_factory(*args, **kwargs):
        kwargs.setdefault("plan_store", jobs)
        return AgentWorker(*args, **kwargs)

    return WorkerRouterDependencies(
        config=config,
        jobs=jobs,
        lifecycle=lifecycle,
        worker_factory=worker_factory,
        project_lock_key=lambda project_root, route: project_lock_key(project_root, route),
        track_agent_session_event=lambda *args, **kwargs: track_agent_session_event(*args, **kwargs),
        ephemeral_worker_events=EPHEMERAL_WORKER_EVENTS,
        coalesce_live_events=lambda events: coalesce_live_events(events),
    )


def _record_choice(config: dict[str, Any], root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return record_choice(config, root, payload, style_mount_service=_STYLE_MOUNTS)


def create_app(config_override: dict[str, Any] | None = None):
    if FastAPI is None:
        raise RuntimeError("Studio API requires pip install -e .[api]")
    config = config_override or load_config()
    lifecycle = ApplicationLifecycleManager(config)
    bootstrap = ApplicationBootstrapService(config, lifecycle)
    jobs = lifecycle.store
    advisor = ProjectAdvisor(config, jobs, runtime_pool=lifecycle.opencode_pool)
    autopilot = AutopilotService(
        config,
        jobs,
        runtime_pool=lifecycle.opencode_pool,
        execution_coordinator=lifecycle.execution_coordinator,
        style_mount_service=_STYLE_MOUNTS,
    )
    narrative_stream_state: dict[str, dict[str, Any]] = {}
    narrative_v3_stream_state: dict[str, dict[str, Any]] = {}
    narrative_stream_lock = threading.Lock()
    app = FastAPI(title="ArcVellum", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        # The packaged WebView talks to the loopback sidecar from a Tauri
        # origin. Its authenticated requests use credentials="include" so the
        # browser requires this response header even when Bearer auth is also
        # present. Vite's same-origin proxy does not exercise this production
        # CORS path, so keep it covered by an API regression test.
        allow_credentials=True,
    )
    api_token = os.environ.get("LES_API_TOKEN", "").strip()
    startup_nonce = os.environ.get("LES_STARTUP_NONCE", "").strip()
    desktop_session_token = secrets.token_urlsafe(32) if api_token else ""

    if api_token:
        @app.middleware("http")
        async def desktop_auth(request: Request, call_next):
            path = request.url.path
            if request.method == "OPTIONS" or path == "/" or path.startswith("/ui/") or path == "/desktop/session":
                return await call_next(request)
            supplied = request.headers.get("Authorization", "")
            session_cookie = request.cookies.get("les_desktop_session", "")
            if supplied == f"Bearer {api_token}" or secrets.compare_digest(session_cookie, desktop_session_token):
                return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "Studio desktop session is not authenticated"})
    app.state.lifecycle = lifecycle
    app.state.bootstrap = bootstrap
    app.state.autopilot = autopilot

    read_models = ProjectReadModels(
        config,
        lifecycle,
        autopilot,
        # Leave this late-bound in the API module so existing instrumentation
        # and contract tests can observe the public dashboard dependency.
        dashboard_builder=lambda root: build_dashboard(config, root),
    )
    cached_read_model = read_models.cached
    dashboard_snapshot = read_models.dashboard
    library_snapshot = read_models.library
    narrative_evidence_snapshot = read_models.narrative_evidence
    reader_snapshot = read_models.reader
    progress_snapshot = read_models.progress
    delivery_snapshot = read_models.delivery
    workspace_snapshot = read_models.workspace

    def shutdown_application():
        autopilot.shutdown()
        bootstrap.shutdown()
        lifecycle.shutdown()

    if hasattr(app, "add_event_handler"):
        app.add_event_handler("shutdown", shutdown_application)
    else:  # FastAPI releases that expose lifecycle handlers only through the router
        app.router.on_shutdown.append(shutdown_application)

    app.include_router(
        build_application_router(
            ApplicationRouterDependencies(
                config=config,
                lifecycle=lifecycle,
                bootstrap=bootstrap,
                version=__version__,
                startup_nonce=startup_nonce,
                api_token=api_token,
                desktop_session_token=desktop_session_token,
                model_connection_status=model_connection_status,
                build_application_info=build_application_info,
                build_legal_documents=build_legal_documents,
                build_diagnostic_report=build_diagnostic_report,
                export_diagnostic_report=export_diagnostic_report,
                stream_read_model=_stream_read_model,
                frontend_file=_frontend_file,
            )
        )
    )

    app.include_router(
        build_runner_router(
            RunnerRouterDependencies(
                config=config,
                lifecycle=lifecycle,
                locate_opencode=lambda settings: locate_opencode(settings),
                verify_opencode=lambda executable: verify_opencode(executable),
                install_pinned_opencode=lambda: install_pinned_opencode(),
                probe_agent_runner=lambda *args, **kwargs: probe_agent_runner(*args, **kwargs),
                provider_catalog=lambda *args, **kwargs: provider_catalog(*args, **kwargs),
                set_api_credential=lambda *args, **kwargs: set_api_credential(*args, **kwargs),
                connect_custom_provider=lambda *args, **kwargs: connect_custom_provider(*args, **kwargs),
                disconnect_provider=lambda *args, **kwargs: disconnect_provider(*args, **kwargs),
                select_model=lambda *args, **kwargs: select_model(*args, **kwargs),
                model_connection_status=lambda settings: model_connection_status(settings),
                cache_model_catalog=bootstrap.record_model_catalog,
            )
        )
    )

    app.include_router(
        build_project_router(
            ProjectRouterDependencies(
                config=config,
                default_projects_root=lambda: default_projects_root(),
                save_config=lambda settings: save_config(settings),
                list_projects=lambda: list_projects(),
                current_project=lambda: current_project(),
                register_project=lambda path: register_project(path),
                validate_project_location=lambda **values: validate_project_location(**values),
                create_project=lambda **values: create_project(**values),
                read_directions=lambda root, limit: read_directions(root, limit=limit),
                record_direction=lambda root, message: record_direction(root, message),
            )
        )
    )

    app.include_router(
        build_quality_router(
            QualityRouterDependencies(
                load_creative_quality_profile=lambda root: load_creative_quality_profile(root),
                save_creative_quality_profile=lambda *args, **kwargs: save_creative_quality_profile(*args, **kwargs),
                style_lint_gate=lambda *args, **kwargs: style_lint_gate(*args, **kwargs),
                lint_punctuation=lambda *args, **kwargs: lint_punctuation(*args, **kwargs),
                load_rhythm_plan=lambda root: load_rhythm_plan(root),
                save_rhythm_plan=lambda *args, **kwargs: save_rhythm_plan(*args, **kwargs),
            )
        )
    )

    app.include_router(
        build_advisor_router(
            AdvisorRouterDependencies(
                config=config,
                jobs=jobs,
                advisor=advisor,
                dashboard_snapshot=dashboard_snapshot,
                persona_catalog=lambda *args, **kwargs: persona_catalog(*args, **kwargs),
                select_persona=lambda *args, **kwargs: select_persona(*args, **kwargs),
                save_custom_persona=lambda *args, **kwargs: save_custom_persona(*args, **kwargs),
                refresh_advisor_inbox=lambda *args, **kwargs: refresh_advisor_inbox(*args, **kwargs),
                save_inbox_settings=lambda *args, **kwargs: save_inbox_settings(*args, **kwargs),
                sse=_sse,
                visible_delta_chunks=_visible_delta_chunks,
                friendly_error=_friendly_error,
            )
        )
    )

    app.include_router(
        build_automation_router(
            AutomationRouterDependencies(
                jobs=jobs,
                autopilot=autopilot,
                lifecycle=lifecycle,
                dashboard_snapshot=dashboard_snapshot,
                build_agent_observability=lambda *args, **kwargs: build_agent_observability(*args, **kwargs),
                sse=_sse,
            )
        )
    )

    app.include_router(
        build_workflow_router(
            WorkflowRouterDependencies(
                config=config,
                lifecycle=lifecycle,
                autopilot=autopilot,
                cached_read_model=cached_read_model,
                dashboard_snapshot=dashboard_snapshot,
                build_activity=lambda *args, **kwargs: build_activity(*args, **kwargs),
                build_task_summary=lambda *args, **kwargs: build_task_summary(*args, **kwargs),
                current_choices=lambda *args, **kwargs: current_choices(*args, **kwargs),
                record_choice=_record_choice,
                stream_read_model=_stream_read_model,
            )
        )
    )

    worker_dependencies = _worker_dependencies(config, jobs, lifecycle)
    app.include_router(
        build_archive_router(
            default_archive_dependencies(
                jobs,
                launch_worker=lambda request: launch_worker(
                    worker_dependencies,
                    WorkerRequest(**request),
                ),
            )
        )
    )

    app.include_router(build_archaeology_router(archaeology_router_dependencies()))

    app.include_router(
        build_library_router(
            LibraryRouterDependencies(
                jobs=jobs,
                cached_read_model=cached_read_model,
                library_snapshot=library_snapshot,
                progress_snapshot=progress_snapshot,
                workspace_snapshot=workspace_snapshot,
                reader_snapshot=reader_snapshot,
                build_reader_manifest=lambda root: build_reader_manifest(root),
                public_reader_manifest=lambda manifest: public_reader_manifest(manifest),
                read_reader_unit=lambda root, unit_id: read_reader_unit(root, unit_id),
                search_reader=lambda root, query, **kwargs: search_reader(root, query, **kwargs),
                stream_read_model=_stream_read_model,
                sse=_sse,
            )
        )
    )

    app.include_router(
        build_narrative_router(
            _narrative_dependencies(
                config,
                cached_read_model,
                dashboard_snapshot,
                narrative_evidence_snapshot,
                narrative_stream_state,
                narrative_v3_stream_state,
                narrative_stream_lock,
            )
        )
    )

    app.include_router(
        build_delivery_router(
            DeliveryRouterDependencies(
                delivery_snapshot=delivery_snapshot,
                resolve_delivery_file=lambda root, relative: resolve_delivery_file(root, relative),
                delivery_content_type=lambda target: delivery_content_type(target),
                stream_read_model=_stream_read_model,
            )
        )
    )

    app.include_router(
        build_style_lab_router(
            style_lab_dependencies(
                config,
                mounts=_STYLE_MOUNTS,
                launch_style_worker=lambda request: launch_worker(
                    worker_dependencies,
                    WorkerRequest(**request),
                ),
            )
        )
    )

    app.include_router(
        build_project_detail_router(
            ProjectDetailRouterDependencies(
                config=config,
                build_dashboard=lambda settings, root: build_dashboard(settings, root),
                build_reader_manifest=lambda root: build_reader_manifest(root),
                public_reader_manifest=lambda manifest: public_reader_manifest(manifest),
                load_creative_quality_profile=lambda root: load_creative_quality_profile(root),
                save_display_field=lambda *args, **kwargs: save_display_field(*args, **kwargs),
                record_ui_note=lambda *args, **kwargs: record_ui_note(*args, **kwargs),
            )
        )
    )

    app.include_router(
        build_worker_router(worker_dependencies)
    )

    return app
