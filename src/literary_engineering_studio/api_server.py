"""Local Studio API: reused core read models plus Agent Worker execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import secrets
import threading
import time
from typing import Any

from . import __version__
from .application_info import build_application_info, build_diagnostic_report, export_diagnostic_report
from .advisor import ProjectAdvisor
from .advisor_inbox import refresh_advisor_inbox, save_inbox_settings
from .advisor_personas import persona_catalog, save_custom_persona, select_persona
from .autopilot import AutopilotService
from .bootstrap import ApplicationBootstrapService
from .config import default_projects_root, load_config, save_config
from .core_bridge import CoreBridge
from .core_read_models import (
    build_activity,
    build_dashboard,
    build_library,
    build_task_summary,
    current_choices,
    mount_style,
    record_choice,
    record_ui_note,
    save_display_field,
    style_library,
    style_mounts,
)
from .delivery import build_delivery, delivery_content_type, resolve_delivery_file
from .lifecycle import ApplicationLifecycleManager
from .model_connections import model_connection_status
from .narrative_projection import build_narrative_projection
from .opencode_binary import install_pinned_opencode, locate_opencode, verify_opencode
from .opencode_control import disconnect_provider, provider_catalog, select_model, set_api_credential
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
from .runtimes import agent_runner_status
from .supervisor import project_lock_key
from .worker import AgentWorker

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
    from pydantic import BaseModel
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
    BaseModel = object


class WorkerRequest(BaseModel):
    project_root: str
    route: str = "scene-development"
    runtime: str = "opencode"
    task_id: str = ""
    scene: str = ""
    idempotency_key: str = ""


class StyleMountRequest(BaseModel):
    project_root: str
    style_library_root: str = ""
    style_id: str


class ProjectCreateRequest(BaseModel):
    parent_directory: str = ""
    title: str
    folder_name: str = ""
    work_type: str = "novel"
    target_length: int = 30000
    premise: str = ""
    genre: str = ""


class ProjectOpenRequest(BaseModel):
    project_root: str


class ProjectLocationRequest(BaseModel):
    mode: str
    project_root: str = ""
    parent_directory: str = ""
    folder_name: str = ""


class ProjectsRootRequest(BaseModel):
    projects_root: str


class DirectionRequest(BaseModel):
    project_root: str
    message: str


class RunnerProbeRequest(BaseModel):
    model: str = ""
    timeout: int = 120


class OpenCodeCredentialRequest(BaseModel):
    provider_id: str
    credential: str


class ModelSelectionRequest(BaseModel):
    model: str


class AdvisorSessionRequest(BaseModel):
    project_root: str
    title: str = "项目问答"


class AdvisorQuestionRequest(BaseModel):
    question: str
    timeout: int = 180
    context: dict[str, Any] | None = None


class AdvisorPersonaSelectionRequest(BaseModel):
    project_root: str
    persona_id: str


class AdvisorCustomPersonaRequest(BaseModel):
    name: str
    tagline: str = ""
    prompt: str
    persona_id: str = ""


class AdvisorInboxReadRequest(BaseModel):
    read: bool = True


class AdvisorInboxSettingsRequest(BaseModel):
    project_root: str
    mode: str = "standard"
    quiet_start: str = "22:30"
    quiet_end: str = "08:00"


class ReaderPositionRequest(BaseModel):
    project_root: str
    unit_id: str
    scroll_ratio: float = 0.0


class ReaderBookmarkRequest(BaseModel):
    project_root: str
    unit_id: str
    enabled: bool = True


class AutopilotPolicyRequest(BaseModel):
    project_root: str
    policy: dict[str, Any]


class AutopilotStartRequest(BaseModel):
    project_root: str
    runtime: str = "opencode"


class AutopilotControlRequest(BaseModel):
    reason: str = "user-request"


class WritebackDecisionRequest(BaseModel):
    decision: str
    reason: str = ""


class WorkerRetryRequest(BaseModel):
    runtime: str = ""


def create_app():
    if FastAPI is None:
        raise RuntimeError("Studio API requires pip install -e .[api]")
    config = load_config()
    lifecycle = ApplicationLifecycleManager(config)
    bootstrap = ApplicationBootstrapService(config, lifecycle)
    jobs = lifecycle.store
    advisor = ProjectAdvisor(config, jobs)
    autopilot = AutopilotService(config, jobs)
    app = FastAPI(title="ArcVellum", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
    api_token = os.environ.get("LES_API_TOKEN", "").strip()
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

    def shutdown_application():
        autopilot.shutdown()
        bootstrap.shutdown()
        lifecycle.shutdown()

    if hasattr(app, "add_event_handler"):
        app.add_event_handler("shutdown", shutdown_application)
    else:  # FastAPI releases that expose lifecycle handlers only through the router
        app.router.on_shutdown.append(shutdown_application)

    @app.get("/", response_class=HTMLResponse)
    def ui_root():
        return _frontend_file("index.html", "text/html; charset=utf-8")

    @app.post("/desktop/session")
    def desktop_session(request: Request):
        if not api_token:
            return {"ok": True, "desktop_auth": "not-required"}
        supplied = request.headers.get("Authorization", "")
        if supplied != f"Bearer {api_token}":
            raise HTTPException(status_code=401, detail="invalid Studio desktop bootstrap token")
        response = JSONResponse({"ok": True, "desktop_auth": "ready"})
        response.set_cookie(
            "les_desktop_session",
            desktop_session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @app.get("/ui/{path:path}")
    def ui_asset(path: str):
        suffix = Path(path).suffix.lower()
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml; charset=utf-8",
            ".webp": "image/webp",
            ".map": "application/json; charset=utf-8",
        }.get(suffix, "text/plain; charset=utf-8")
        return _frontend_file(path, content_type)

    @app.get("/health")
    def health():
        snapshot = bootstrap.snapshot()
        engine_step = next(
            (item for item in snapshot.get("steps", []) if item.get("id") == "engine_registry"),
            {},
        )
        application_state = lifecycle.health()
        return {
            "ok": True,
            "version": __version__,
            "engine_ready": engine_step.get("status") == "ready",
            "engine_detail": str(engine_step.get("detail") or ""),
            "agent_runners": application_state.get("agent_runners", []),
            "model_connections": model_connection_status(config),
            "model_connection_policy": "runner-managed",
            "application": application_state,
        }

    @app.get("/application/health")
    def application_health():
        return {"ok": True, **lifecycle.health()}

    @app.get("/application/info")
    def application_info():
        return build_application_info(config)

    @app.get("/application/diagnostics")
    def application_diagnostics():
        return {"ok": True, **build_diagnostic_report(config, lifecycle, bootstrap)}

    @app.post("/application/diagnostics/export")
    def application_diagnostics_export():
        target = export_diagnostic_report(config, lifecycle, bootstrap)
        return FileResponse(target, media_type="application/json", filename=target.name)

    @app.get("/application/bootstrap")
    def application_bootstrap():
        return bootstrap.snapshot()

    @app.get("/application/bootstrap/stream")
    def application_bootstrap_stream(interval_seconds: float = 1.0, max_events: int = 0):
        return _stream_read_model(
            "application.bootstrap",
            bootstrap.snapshot,
            interval_seconds,
            max_events,
        )

    @app.post("/application/warmup")
    def application_warmup():
        started = bootstrap.start_warmup(force=True)
        return {"ok": True, "started": started, "bootstrap": bootstrap.snapshot()}

    @app.get("/agent-runners")
    def agent_runners():
        return {"ok": True, "items": agent_runner_status(config, force_refresh=True)}

    @app.get("/agent-runners/opencode/bundle")
    def opencode_bundle_status():
        executable = locate_opencode(
            config.get("agent_runners", {}).get("opencode", {})
            if isinstance(config.get("agent_runners"), dict)
            else {}
        )
        return {
            "ok": True,
            "installed": executable is not None,
            "verification": verify_opencode(executable) if executable else {},
        }

    @app.post("/agent-runners/opencode/install")
    def opencode_bundle_install():
        return _call(lambda: {"ok": True, **install_pinned_opencode()})

    @app.post("/agent-runners/{runner_id}/probe")
    def agent_runner_probe(runner_id: str, payload: RunnerProbeRequest):
        if runner_id not in {"opencode", "claude-code", "codex-cli"}:
            raise HTTPException(status_code=404, detail="unknown Agent Runner")
        return _call(
            lambda: {
                "ok": True,
                **probe_agent_runner(config, runner_id, model=payload.model, timeout=max(10, min(600, payload.timeout))),
            }
        )

    @app.get("/model-connections/opencode/catalog")
    def opencode_model_catalog():
        return _call(lambda: {"ok": True, **provider_catalog(config)})

    @app.put("/model-connections/opencode/credential")
    def opencode_model_credential(payload: OpenCodeCredentialRequest):
        return _call(lambda: {"ok": True, **set_api_credential(config, payload.provider_id, payload.credential)})

    @app.delete("/model-connections/opencode/credential/{provider_id}")
    def opencode_model_disconnect(provider_id: str):
        return _call(lambda: {"ok": True, **disconnect_provider(config, provider_id)})

    @app.put("/model-connections/opencode/model")
    def opencode_model_select(payload: ModelSelectionRequest):
        return _call(lambda: {"ok": True, **select_model(config, payload.model)})

    @app.get("/model-connections")
    def model_connections():
        return {
            "ok": True,
            "items": model_connection_status(config),
            "managed_by": "agent-runner",
        }

    @app.get("/advisor/sessions")
    def advisor_sessions(project_root: str):
        return _call(lambda: {"ok": True, "items": advisor.list_sessions(_project(project_root))})

    @app.get("/advisor/personas")
    def advisor_personas(project_root: str):
        return _call(lambda: persona_catalog(advisor._data_root(), _project(project_root)))

    @app.put("/advisor/personas/selection")
    def advisor_persona_selection(payload: AdvisorPersonaSelectionRequest):
        return _call(
            lambda: select_persona(advisor._data_root(), _project(payload.project_root), payload.persona_id)
        )

    @app.put("/advisor/personas/custom")
    def advisor_persona_custom(payload: AdvisorCustomPersonaRequest):
        return _call(
            lambda: save_custom_persona(
                advisor._data_root(),
                name=payload.name,
                tagline=payload.tagline,
                prompt=payload.prompt,
                persona_id=payload.persona_id,
            )
        )

    @app.get("/advisor/inbox")
    def advisor_inbox(project_root: str):
        return _call(lambda: refresh_advisor_inbox(config, jobs, _project(project_root)))

    @app.patch("/advisor/inbox/{item_id}")
    def advisor_inbox_read(item_id: str, payload: AdvisorInboxReadRequest):
        return _call(lambda: {"ok": True, "item": jobs.mark_advisor_inbox_read(item_id, read=payload.read)})

    @app.put("/advisor/inbox/settings")
    def advisor_inbox_settings(payload: AdvisorInboxSettingsRequest):
        return _call(
            lambda: {
                "ok": True,
                "settings": save_inbox_settings(
                    advisor._data_root(),
                    _project(payload.project_root),
                    {
                        "mode": payload.mode,
                        "quiet_start": payload.quiet_start,
                        "quiet_end": payload.quiet_end,
                    },
                ),
            }
        )

    @app.get("/advisor/inbox/stream")
    def advisor_inbox_stream(project_root: str, interval_seconds: float = 8.0, max_events: int = 0):
        root = _project(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 8.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            previous = ""
            sent = 0
            while True:
                snapshot = refresh_advisor_inbox(config, jobs, root)
                signature = json.dumps(snapshot.get("items", []), ensure_ascii=False, sort_keys=True)
                if signature != previous:
                    yield _sse("advisor.inbox", snapshot)
                    previous = signature
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": advisor inbox heartbeat\n\n"
                time.sleep(interval)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/advisor/sessions")
    def advisor_session_create(payload: AdvisorSessionRequest):
        return _call(lambda: {"ok": True, **advisor.create_session(_project(payload.project_root), title=payload.title)})

    @app.get("/advisor/sessions/{session_id}")
    def advisor_session_read(session_id: str):
        return _call(lambda: {"ok": True, **jobs.read_advisor_session(session_id)})

    @app.post("/advisor/sessions/{session_id}/ask")
    def advisor_session_ask(session_id: str, payload: AdvisorQuestionRequest):
        return _call(
            lambda: {
                "ok": True,
                "session_id": session_id,
                "answer": advisor.ask(
                    session_id,
                    payload.question,
                    timeout=max(10, min(600, payload.timeout)),
                    context=payload.context or {},
                ),
            }
        )

    @app.post("/advisor/sessions/{session_id}/ask/stream")
    def advisor_session_ask_stream(session_id: str, payload: AdvisorQuestionRequest):
        events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()

        def emit(event: str, data: dict[str, Any]) -> None:
            events.put((event, data))

        def run() -> None:
            try:
                result = advisor.ask(
                    session_id,
                    payload.question,
                    timeout=max(10, min(600, payload.timeout)),
                    context=payload.context or {},
                    event_sink=emit,
                )
                events.put(("advisor.result", {"answer": result}))
            except Exception as exc:
                events.put(("advisor.error", {"message": _friendly_error(exc)}))
            finally:
                events.put(("advisor.closed", {}))

        threading.Thread(target=run, name=f"arcvellum-advisor-{session_id}", daemon=True).start()

        def stream():
            yield _sse("advisor.opened", {"session_id": session_id})
            while True:
                try:
                    event, data = events.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(event, data)
                if event == "advisor.closed":
                    break

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/autopilot/status")
    def autopilot_status(project_root: str):
        def read():
            payload = autopilot.status(_project(project_root))
            run = payload.get("run")
            payload["decisions"] = jobs.delegated_decisions(run["run_id"])[-20:] if run else []
            return payload
        return _call(read)

    @app.put("/autopilot/policy")
    def autopilot_policy_save(payload: AutopilotPolicyRequest):
        return _call(lambda: {"ok": True, **autopilot.save_policy(_project(payload.project_root), payload.policy)})

    @app.post("/autopilot/start")
    def autopilot_start(payload: AutopilotStartRequest):
        return _call(lambda: {"ok": True, "run": autopilot.start(_project(payload.project_root), runtime=payload.runtime)})

    @app.post("/autopilot/runs/{run_id}/pause")
    def autopilot_pause(run_id: str, payload: AutopilotControlRequest):
        return _call(lambda: {"ok": True, "run": autopilot.pause(run_id, reason=payload.reason)})

    @app.post("/autopilot/runs/{run_id}/resume")
    def autopilot_resume(run_id: str):
        return _call(lambda: {"ok": True, "run": autopilot.resume(run_id)})

    @app.get("/autopilot/runs/{run_id}/events")
    def autopilot_events(run_id: str, after: int = 0, limit: int = 300):
        return _call(lambda: {"ok": True, "items": jobs.autopilot_events_since(run_id, after, limit=limit)})

    @app.get("/autopilot/runs/{run_id}/stream")
    def autopilot_stream(run_id: str, after: int = 0):
        jobs.read_autopilot_run(run_id)

        def stream():
            cursor = max(0, int(after))
            while True:
                items = jobs.autopilot_events_since(run_id, cursor)
                for item in items:
                    cursor = max(cursor, int(item["sequence"]))
                    yield _sse(str(item["event"]), item)
                run = jobs.read_autopilot_run(run_id)
                yield _sse("autopilot.status", {"run": run, "cursor": cursor})
                if run["status"] in {"complete", "paused", "blocked", "cancelled", "failed"}:
                    break
                time.sleep(0.7)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/runtime/adapters")
    def runtime_adapters():
        return {
            "ok": True,
            "items": agent_runner_status(config),
            "deprecated_alias": True,
            "replacement": "/agent-runners",
        }

    @app.get("/projects")
    def projects_index():
        return {"ok": True, **list_projects()}

    @app.get("/projects/current")
    def projects_current():
        return current_project()

    @app.get("/projects/default-location")
    def projects_default_location():
        application = config.get("application") if isinstance(config.get("application"), dict) else {}
        root = Path(str(application.get("projects_root") or default_projects_root())).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return {
            "ok": True,
            "projects_root": str(root),
            "source": str(application.get("projects_root_source") or "platform-default"),
            "portable_mode": bool(application.get("portable_mode", False)),
        }

    @app.put("/projects/default-location")
    def projects_default_location_update(payload: ProjectsRootRequest):
        root = Path(payload.projects_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir() or not os.access(root, os.W_OK):
            raise HTTPException(status_code=400, detail="默认作品库必须是可写入的文件夹。")
        application = config.setdefault("application", {})
        application["projects_root"] = str(root)
        application["projects_root_source"] = "user-selected"
        save_config(config)
        return {"ok": True, "projects_root": str(root), "source": "user-selected", "affects_existing_projects": False}

    @app.post("/projects/open")
    def projects_open(payload: ProjectOpenRequest):
        return _call(lambda: {"ok": True, "project": register_project(payload.project_root)})

    @app.post("/projects/validate-location")
    def projects_validate_location(payload: ProjectLocationRequest):
        values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return _call(lambda: {"ok": True, **validate_project_location(**values)})

    @app.post("/projects/create")
    def projects_create(payload: ProjectCreateRequest):
        values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return _call(lambda: {"ok": True, "project": create_project(**values)})

    @app.get("/projects/directions")
    def projects_directions(project_root: str, limit: int = 20):
        root = _project(project_root)
        return {"ok": True, "items": read_directions(root, limit=limit)}

    @app.post("/projects/directions")
    def projects_record_direction(payload: DirectionRequest):
        return _call(lambda: record_direction(_project(payload.project_root), payload.message))

    @app.post("/worker/prepare")
    def worker_prepare(payload: WorkerRequest):
        try:
            task, sandbox, terminal = AgentWorker(config).prepare(
                _project(payload.project_root),
                route=payload.route,
                runtime_id=payload.runtime,
                task_id=payload.task_id,
                scene=payload.scene,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if terminal:
            return {"ok": True, **terminal.as_dict()}
        assert task is not None and sandbox is not None
        return {
            "ok": True,
            "status": "prepared",
            "task_id": task.task_id,
            "route": task.route,
            "runtime": payload.runtime,
            "execution_contract": task.execution_contract.as_dict(),
            "run_root": str(sandbox.run_root),
            "workspace": str(sandbox.workspace),
            "prompt": str(sandbox.prompt_path),
        }

    @app.post("/worker/run")
    def worker_run(payload: WorkerRequest):
        request_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        job = jobs.create(request_data, idempotency_key=payload.idempotency_key)

        def execute(cancel_event) -> dict[str, Any]:
            def emit(event: str, data: dict[str, Any]) -> None:
                jobs.append_event(str(job["job_id"]), event, data)
                if event == "sandbox.prepared":
                    jobs.register_resources(
                        str(job["job_id"]),
                        formal_project=str(data.get("project_root") or payload.project_root),
                        task_sandbox=str(data.get("run_root") or ""),
                        agent_session=f"{data.get('runner_id') or payload.runtime}:{data.get('run_id') or job['job_id']}",
                        run_workspace=str(data.get("workspace") or ""),
                    )

            result = AgentWorker(config, event_sink=emit, cancel_event=cancel_event).run_once(
                _project(payload.project_root),
                route=payload.route,
                runtime_id=payload.runtime,
                task_id=payload.task_id,
                scene=payload.scene,
            )
            return result.as_dict()

        if job["status"] in {"queued", "interrupted"}:
            lifecycle.supervisor.submit(
                str(job["job_id"]),
                execute,
                lock_key=project_lock_key(payload.project_root, payload.route),
            )
        return {"ok": True, **job}

    @app.get("/worker/jobs/{job_id}")
    def worker_job(job_id: str):
        try:
            return {"ok": True, **jobs.read(job_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/worker/jobs/{job_id}/events")
    def worker_job_events(job_id: str, after: int = 0, limit: int = 200):
        try:
            jobs.read(job_id)
            return {"ok": True, "items": jobs.events_since(job_id, after, limit=limit)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/worker/jobs/{job_id}/stop")
    def worker_job_stop(job_id: str):
        try:
            return {"ok": True, **lifecycle.supervisor.stop(job_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/worker/jobs/{job_id}/writeback")
    def worker_job_writeback(job_id: str, payload: WritebackDecisionRequest):
        try:
            job = jobs.read(job_id)
            if job["status"] != "waiting_writeback":
                raise ValueError("job is not waiting for writeback approval")
            run_root = Path(str(job.get("result", {}).get("run_root") or ""))
            request = job.get("request") if isinstance(job.get("request"), dict) else {}
            lock_key = project_lock_key(str(request.get("project_root") or ""), str(request.get("route") or "auto"))
            owner = lifecycle.supervisor.worker_id
            if not jobs.acquire_lock(lock_key, job_id, owner, lease_seconds=180):
                raise RuntimeError("another active task owns this project route")
            try:
                def emit(event: str, data: dict[str, Any]) -> None:
                    jobs.append_event(job_id, event, data)

                worker = AgentWorker(config, event_sink=emit)
                decision = payload.decision.strip().lower()
                if decision == "approve":
                    result = worker.approve_writeback(run_root, approved_by="studio-user")
                elif decision == "reject":
                    result = worker.reject_writeback(run_root, rejected_by="studio-user", reason=payload.reason)
                else:
                    raise ValueError("writeback decision must be approve or reject")
                return {
                    "ok": True,
                    **jobs.update(
                        job_id,
                        status=result.status,
                        result=result.as_dict(),
                        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    ),
                }
            finally:
                jobs.release_lock(lock_key, job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/worker/jobs/{job_id}/retry")
    def worker_job_retry(job_id: str, payload: WorkerRetryRequest):
        try:
            previous = jobs.read(job_id)
            if previous["status"] in {"queued", "running", "stopping"}:
                raise ValueError("active jobs cannot be retried")
            request = dict(previous.get("request") or {})
            if payload.runtime.strip():
                if payload.runtime not in {"opencode", "host-agent", "claude-code", "codex-cli"}:
                    raise ValueError("unknown Agent Runner")
                request["runtime"] = payload.runtime
            request["idempotency_key"] = ""
            retry = WorkerRequest(**request)
            return worker_run(retry)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/worker/jobs/{job_id}/stream")
    def worker_job_stream(job_id: str, request: Request, interval_seconds: float = 0.5, after: int = 0):
        interval = max(0.1, min(10.0, float(interval_seconds or 0.5)))
        try:
            resume_after = max(int(after), int(request.headers.get("Last-Event-ID") or 0))
        except ValueError:
            resume_after = max(0, int(after))

        def stream():
            cursor = max(0, resume_after)
            previous_revision = -1
            while True:
                payload = jobs.read(job_id)
                for item in jobs.events_since(job_id, cursor):
                    cursor = int(item["sequence"])
                    yield f"id: {cursor}\n"
                    yield f"event: {item['event']}\n"
                    yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                revision = int(payload.get("revision") or 0)
                if revision != previous_revision:
                    yield "event: worker\n"
                    yield "data: " + json.dumps({"ok": True, **payload}, ensure_ascii=False) + "\n\n"
                    previous_revision = revision
                if payload.get("status") not in {"queued", "running", "stopping"}:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/workflow/dashboard")
    def workflow_dashboard(project_root: str):
        return _call(lambda: build_dashboard(config, _project(project_root)))

    @app.get("/workflow/dashboard/stream")
    def workflow_dashboard_stream(project_root: str, interval_seconds: float = 8.0, max_events: int = 0):
        return _stream_read_model(
            "dashboard",
            lambda: build_dashboard(config, _project(project_root)),
            interval_seconds,
            max_events,
        )

    @app.get("/workflow/activity")
    def workflow_activity(project_root: str, limit: int = 30):
        return _call(lambda: build_activity(config, _project(project_root), max(1, min(200, limit))))

    @app.get("/workflow/activity/stream")
    def workflow_activity_stream(project_root: str, interval_seconds: float = 4.0, max_events: int = 0):
        return _stream_read_model(
            "activity",
            lambda: build_activity(config, _project(project_root)),
            interval_seconds,
            max_events,
        )

    @app.get("/workflow/task-package")
    def workflow_task_package(project_root: str, task_id: str):
        return _call(lambda: build_task_summary(config, _project(project_root), task_id))

    @app.get("/workflow/current-choice")
    def workflow_current_choice(project_root: str):
        return _call(lambda: current_choices(config, _project(project_root)))

    @app.post("/workflow/human-choice")
    def workflow_human_choice(payload: dict[str, Any]):
        return _call(lambda: record_choice(config, _project(str(payload.get("project_root") or "")), payload))

    @app.get("/project/library")
    def project_library(project_root: str):
        return _call(lambda: build_library(config, _project(project_root)))

    @app.get("/project/library/stream")
    def project_library_stream(project_root: str, interval_seconds: float = 6.0, max_events: int = 0):
        return _stream_read_model(
            "library",
            lambda: build_library(config, _project(project_root)),
            interval_seconds,
            max_events,
        )

    @app.get("/reader/manifest")
    def reader_manifest(project_root: str):
        return _call(lambda: public_reader_manifest(build_reader_manifest(_project(project_root))))

    @app.get("/reader/units/{unit_id}")
    def reader_unit(unit_id: str, project_root: str):
        return _call(lambda: read_reader_unit(_project(project_root), unit_id))

    @app.get("/reader/search")
    def reader_search(project_root: str, q: str, limit: int = 40):
        return _call(lambda: search_reader(_project(project_root), q, limit=limit))

    @app.get("/reader/state")
    def reader_state(project_root: str):
        root = _project(project_root)
        return {"ok": True, "schema": "arcvellum/reader-state/v1", **jobs.reader_state(str(root))}

    @app.put("/reader/position")
    def reader_position(payload: ReaderPositionRequest):
        root = _project(payload.project_root)
        return {"ok": True, "schema": "arcvellum/reader-state/v1", **jobs.save_reader_position(str(root), payload.unit_id, payload.scroll_ratio)}

    @app.put("/reader/bookmark")
    def reader_bookmark(payload: ReaderBookmarkRequest):
        root = _project(payload.project_root)
        return {"ok": True, "schema": "arcvellum/reader-state/v1", **jobs.set_reader_bookmark(str(root), payload.unit_id, payload.enabled)}

    @app.get("/reader/stream")
    def reader_stream(project_root: str, interval_seconds: float = 4.0, max_events: int = 0):
        root = _project(project_root)
        interval = max(1.0, min(60.0, float(interval_seconds or 4.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            previous: dict[str, Any] | None = None
            while True:
                manifest = public_reader_manifest(build_reader_manifest(root))
                revision = str(manifest.get("project_revision") or "")
                if previous is None or revision != str(previous.get("project_revision") or ""):
                    previous_ids = {str(item.get("unit_id")) for item in (previous or {}).get("units", []) if isinstance(item, dict)}
                    current_ids = {str(item.get("unit_id")) for item in manifest.get("units", []) if isinstance(item, dict)}
                    payload = {
                        **manifest,
                        "delta": {
                            "added": sorted(current_ids - previous_ids),
                            "removed": sorted(previous_ids - current_ids),
                            "initial": previous is None,
                        },
                    }
                    yield _sse("reader.manifest", payload)
                    previous = manifest
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": reader heartbeat\n\n"
                time.sleep(interval)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/narrative/projection")
    def narrative_projection(project_root: str, level: str = "book", focus: str = ""):
        return _call(lambda: build_narrative_projection(config, _project(project_root), level=level, focus=focus))

    @app.get("/narrative/stream")
    def narrative_stream(project_root: str, level: str = "book", focus: str = "", interval_seconds: float = 6.0, max_events: int = 0):
        root = _project(project_root)
        interval = max(2.0, min(60.0, float(interval_seconds or 6.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            previous = ""
            sent = 0
            while True:
                projection = build_narrative_projection(config, root, level=level, focus=focus)
                revision = str(projection.get("revision") or "")
                if revision != previous:
                    yield _sse("narrative.projection", projection)
                    previous = revision
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": narrative heartbeat\n\n"
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.patch("/project/display-field")
    def project_display_field(payload: dict[str, Any]):
        return _call(lambda: save_display_field(config, _project(str(payload.get("project_root") or "")), payload))

    @app.post("/project/ui-note")
    def project_ui_note(payload: dict[str, Any]):
        return _call(lambda: record_ui_note(config, _project(str(payload.get("project_root") or "")), payload))

    @app.get("/project/delivery")
    def project_delivery(project_root: str):
        return _call(lambda: build_delivery(config, _project(project_root)))

    @app.get("/project/delivery/download")
    def project_delivery_download(project_root: str, path: str):
        root = _project(project_root)
        try:
            target = resolve_delivery_file(root, path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FileResponse(
            target,
            media_type=delivery_content_type(target),
            filename=target.name,
        )

    @app.get("/style-lab/library")
    def style_lab_library(style_library_root: str = ""):
        return _call(lambda: style_library(config, style_library_root))

    @app.get("/style-lab/mounts")
    def style_lab_mounts(project_root: str):
        return _call(lambda: style_mounts(config, _project(project_root)))

    @app.post("/style-lab/mount")
    def style_lab_mount(payload: StyleMountRequest):
        return _call(
            lambda: mount_style(
                config,
                _project(payload.project_root),
                payload.style_library_root,
                payload.style_id,
            )
        )

    return app


def _call(function):
    try:
        return function()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _friendly_error(exc: Exception) -> str:
    value = str(exc).strip()
    replacements = {
        "bundled OpenCode Runner is not installed": "创作顾问尚未准备好，请先在“设置”中完成 Agent 连接。",
        "select an OpenCode provider/model before using the advisor": "请先在“设置”中选择顾问使用的模型。",
        "advisor answer timed out": "这次思考时间有点久，请稍后重试。",
        "read-only advisor project integrity check failed": "作品在顾问思考期间发生了内容变化，请重新提问以读取最新版本。",
    }
    return replacements.get(value, value or "顾问暂时没有完成回答，请重试。")


def _stream_read_model(event: str, function, interval_seconds: float, max_events: int):
    interval = max(1.0, min(60.0, float(interval_seconds or 4.0)))
    limit = max(0, int(max_events or 0))

    def stream():
        sent = 0
        while True:
            payload = function()
            yield f"event: {event}\n"
            yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            sent += 1
            if limit and sent >= limit:
                break
            time.sleep(interval)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _project(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir() or not (path / "project.yaml").exists():
        raise ValueError(f"not a Literary Engineering work project: {path}")
    return path


def _frontend_file(relative: str, content_type: str):
    root = Path(__file__).resolve().with_name("frontend")
    candidates = [root / "dist" / relative]
    target = next((candidate.resolve() for candidate in candidates if candidate.resolve().is_file()), None)
    if target is None or not target.is_relative_to(root.resolve()):
        raise HTTPException(status_code=404, detail=f"frontend asset not found: {relative}")
    data = target.read_bytes()
    if content_type.startswith("text/") or "javascript" in content_type:
        return Response(content=data.decode("utf-8"), media_type=content_type)
    return Response(content=data, media_type=content_type)
