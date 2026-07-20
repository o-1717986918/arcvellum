"""Local Studio API: reused core read models plus Agent Worker execution."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from . import __version__
from .config import load_config, repository_root
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
from .jobs import JobStore
from .runtimes import runtime_status
from .worker import AgentWorker

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, Response, StreamingResponse
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    FastAPI = None
    HTTPException = None
    HTMLResponse = None
    Response = None
    StreamingResponse = None
    BaseModel = object


class WorkerRequest(BaseModel):
    project_root: str
    route: str = "scene-development"
    runtime: str = "host-agent"
    task_id: str = ""
    scene: str = ""


class StyleMountRequest(BaseModel):
    project_root: str
    style_library_root: str = ""
    style_id: str


def create_app():
    if FastAPI is None:
        raise RuntimeError("Studio API requires pip install -e .[api]")
    config = load_config()
    runs_root = Path(str(config.get("worker", {}).get("runs_root") or ""))
    jobs = JobStore(runs_root / "jobs")
    app = FastAPI(title="Literary Engineering Studio", version=__version__)

    @app.get("/", response_class=HTMLResponse)
    def ui_root():
        return _frontend_file("index.html", "text/html; charset=utf-8")

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
        }.get(suffix, "text/plain; charset=utf-8")
        return _frontend_file(path, content_type)

    @app.get("/health")
    def health():
        try:
            core = CoreBridge(config).doctor()
            core_ready = core.returncode == 0
            core_detail = core.stderr.strip() if core.returncode else "ready"
        except Exception as exc:
            core_ready = False
            core_detail = str(exc)
        return {
            "ok": True,
            "version": __version__,
            "core_ready": core_ready,
            "core_detail": core_detail,
            "runtimes": runtime_status(config),
            "model_provider": "disabled-by-architecture",
        }

    @app.get("/runtime/adapters")
    def runtime_adapters():
        return {"ok": True, "items": runtime_status(config), "model_provider": "not used"}

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
            "run_root": str(sandbox.run_root),
            "workspace": str(sandbox.workspace),
            "prompt": str(sandbox.prompt_path),
        }

    @app.post("/worker/run")
    def worker_run(payload: WorkerRequest):
        request_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        job = jobs.create(request_data)

        def execute() -> dict[str, Any]:
            result = AgentWorker(config).run_once(
                _project(payload.project_root),
                route=payload.route,
                runtime_id=payload.runtime,
                task_id=payload.task_id,
                scene=payload.scene,
            )
            return result.as_dict()

        jobs.start(str(job["job_id"]), execute)
        return {"ok": True, **job}

    @app.get("/worker/jobs/{job_id}")
    def worker_job(job_id: str):
        try:
            return {"ok": True, **jobs.read(job_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/worker/jobs/{job_id}/stream")
    def worker_job_stream(job_id: str, interval_seconds: float = 1.0):
        interval = max(0.5, min(10.0, float(interval_seconds or 1.0)))

        def stream():
            previous = ""
            while True:
                payload = jobs.read(job_id)
                serialized = json.dumps({"ok": True, **payload}, ensure_ascii=False)
                if serialized != previous:
                    yield "event: worker\n"
                    yield "data: " + serialized + "\n\n"
                    previous = serialized
                if payload.get("status") not in {"queued", "running"}:
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

    @app.patch("/project/display-field")
    def project_display_field(payload: dict[str, Any]):
        return _call(lambda: save_display_field(config, _project(str(payload.get("project_root") or "")), payload))

    @app.post("/project/ui-note")
    def project_ui_note(payload: dict[str, Any]):
        return _call(lambda: record_ui_note(config, _project(str(payload.get("project_root") or "")), payload))

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
    root = repository_root() / "frontend"
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise HTTPException(status_code=404, detail=f"frontend asset not found: {relative}")
    data = target.read_bytes()
    if content_type.startswith("text/") or "javascript" in content_type:
        return Response(content=data.decode("utf-8"), media_type=content_type)
    return Response(content=data, media_type=content_type)
