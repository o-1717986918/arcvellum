"""Project library, display editing and initialization endpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ...demo_project import build_demo_project
from ...init_project import InitOptions, init_work_project
from ...model_config import config_path
from ...project_interaction import build_editable_schema, record_ui_note, save_display_field
from ...project_library import build_project_library, find_project_library_item
from ...style_lab import active_project_style
from ..common import (
    ensure_target_allowed,
    read_text,
    rel_str,
    require_api_token,
    safe_project_root,
    tail_jsonl,
)
from ..models import DemoProjectRequest, DisplayFieldRequest, InitProjectRequest, UiNoteRequest

try:
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import StreamingResponse
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    HTTPException = None
    Request = object
    StreamingResponse = None


def build_project_router(*, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.get("/project/summary")
    def project_summary(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        return project_summary_payload(safe_project_root(project_root, allowed_roots))

    @router.get("/project/library")
    def project_library(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            return {"ok": True, **build_project_library(root)}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/project/library/item")
    def project_library_item(project_root: str, kind: str, item_id: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            return find_project_library_item(root, kind, item_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/project/library/stream")
    def project_library_stream(project_root: str, http_request: Request, interval_seconds: float = 6.0, max_events: int = 0):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        interval = max(2.0, min(60.0, float(interval_seconds or 6.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            while True:
                payload = {"ok": True, **build_project_library(root)}
                yield "event: library\n"
                yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.get("/project/editable-schema")
    def project_editable_schema(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        return {"ok": True, **build_editable_schema(root)}

    @router.patch("/project/display-field")
    def project_display_field(payload: DisplayFieldRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            return save_display_field(root, target_type=payload.target_type, target_id=payload.target_id, field=payload.field, value=payload.value, actor=payload.actor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/project/ui-note")
    def project_ui_note(payload: UiNoteRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            return record_ui_note(root, target_type=payload.target_type, target_id=payload.target_id, note=payload.note, actor=payload.actor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/project/init")
    def project_init(payload: InitProjectRequest, http_request: Request):
        require_api_token(http_request, api_token)
        target = Path(payload.target).resolve()
        ensure_target_allowed(target, allowed_roots)
        try:
            result = init_work_project(InitOptions(target=target, title=payload.title, premise=payload.premise, genre=payload.genre, work_type=payload.work_type, target_length=payload.target_length, language=payload.language))
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "root": str(result.root), "files": [file.relative_to(result.root).as_posix() for file in result.files]}

    @router.post("/project/demo")
    def project_demo(payload: DemoProjectRequest, http_request: Request):
        require_api_token(http_request, api_token)
        target = Path(payload.target).resolve()
        ensure_target_allowed(target, allowed_roots)
        try:
            result = build_demo_project(target, title=payload.title, run_agent_workflow=payload.run_agent_workflow)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "root": str(result.root), "report": rel_str(result.report_path, result.root), "workflow_state": rel_str(result.workflow_state, result.root) if result.workflow_state else ""}

    return router


def project_summary_payload(root: Path) -> dict[str, object]:
    workflow_index = root / "workflow" / "runs" / "index.jsonl"
    approval_index = root / "workflow" / "approvals" / "index.jsonl"
    return {
        "root": str(root),
        "project_yaml": read_text(root / "project.yaml", 4000),
        "has_project": (root / "project.yaml").exists(),
        "counts": {
            "characters": len(list((root / "characters").glob("*.yaml"))) if (root / "characters").exists() else 0,
            "scenes": len(list((root / "scenes").glob("*.yaml"))) if (root / "scenes").exists() else 0,
            "drafts": len(list((root / "drafts" / "scenes").glob("*.md"))) if (root / "drafts" / "scenes").exists() else 0,
            "agent_runs": len(list((root / "agents" / "runs").iterdir())) if (root / "agents" / "runs").exists() else 0,
        },
        "paths": {"agents": str(root / "agents"), "reviews": str(root / "reviews"), "workflow_runs": str(root / "workflow" / "runs"), "config": str(config_path())},
        "active_style_skill": active_project_style(root),
        "recent_runs": tail_jsonl(workflow_index, 8),
        "approval_records": len(tail_jsonl(approval_index, 1000)),
    }
