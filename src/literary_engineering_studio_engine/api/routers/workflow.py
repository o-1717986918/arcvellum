"""Workflow, approval and Canon HTTP endpoints for the legacy Engine API."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ...approval import record_workflow_approval
from ...canon_evolver import apply_canon_patch, build_canon_patch_backlog
from ...project_interaction import build_current_human_choices, record_human_choice
from ...workflow_activity import build_task_package_summary, build_workflow_activity
from ...workflow.dashboard_projection import project_workflow_dashboard
from ...workflow_runner import run_workflow
from ..common import rel_str, reject_bypass, require_api_token, run_state_path, safe_project_root, safe_relative_path
from ..models import ApprovalRequest, CanonApplyRequest, HumanChoiceRequest, RunWorkflowRequest

try:
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import StreamingResponse
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    HTTPException = None
    Request = object
    StreamingResponse = None


def build_workflow_router(*, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.post("/workflow/run")
    def workflow_run(payload: RunWorkflowRequest, http_request: Request):
        require_api_token(http_request, api_token)
        reject_bypass(payload, "POST /workflow/run")
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = run_workflow(root, mode=payload.mode, scene=Path(payload.scene), chapter_id=payload.chapter_id, target_length=payload.target_length, include_blocked=payload.include_blocked, overwrite_draft=payload.overwrite_draft, generate_candidate=payload.generate_candidate, promote_candidate=payload.promote_candidate, agent_review=payload.agent_review, agent_tasks=payload.agent_tasks, provider=payload.provider, run_id=payload.run_id or None, resumed_from=payload.resume_run_id, overwrite_run=payload.overwrite_run)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return run_response(result, root)

    @router.get("/workflow/dashboard")
    def workflow_dashboard(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            payload = project_workflow_dashboard(root)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return dashboard_response(payload, root)

    @router.get("/workflow/dashboard/stream")
    def workflow_dashboard_stream(project_root: str, http_request: Request, interval_seconds: float = 8.0, max_events: int = 0):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        interval = max(3.0, min(60.0, float(interval_seconds or 8.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            while True:
                payload = project_workflow_dashboard(root)
                yield "event: dashboard\n"
                yield "data: " + json.dumps(dashboard_response(payload, root), ensure_ascii=False) + "\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.get("/workflow/activity")
    def workflow_activity(project_root: str, http_request: Request, limit: int = 30):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            return {"ok": True, **build_workflow_activity(root, limit=max(1, min(200, int(limit or 30))))}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/workflow/activity/stream")
    def workflow_activity_stream(project_root: str, http_request: Request, interval_seconds: float = 4.0, max_events: int = 0):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        interval = max(2.0, min(60.0, float(interval_seconds or 4.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            while True:
                yield "event: activity\n"
                yield "data: " + json.dumps({"ok": True, **build_workflow_activity(root)}, ensure_ascii=False) + "\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.get("/workflow/task-package")
    def workflow_task_package(project_root: str, task_id: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            return {"ok": True, **build_task_package_summary(root, task_id)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/workflow/current-choice")
    def workflow_current_choice(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            return {"ok": True, **build_current_human_choices(root)}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/workflow/human-choice")
    def workflow_human_choice(payload: HumanChoiceRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            value = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
            return record_human_choice(root, value)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/canon/backlog")
    def canon_backlog(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            result = build_canon_patch_backlog(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "project_root": str(root), "summary": payload.get("summary", {}), "items": payload.get("items", []), "paths": {"markdown": rel_str(result.output_path, root), "json": rel_str(result.json_path, root)}}

    @router.post("/canon/apply")
    def canon_apply(payload: CanonApplyRequest, http_request: Request):
        require_api_token(http_request, api_token)
        reject_bypass(payload, "POST /canon/apply")
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = apply_canon_patch(root, patch=Path(payload.patch) if payload.patch else None, approval_run_id=payload.approval_run_id, allow_unapproved=payload.allow_unapproved)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "project_root": str(root), "patch": rel_str(result.patch_path, root), "report": rel_str(result.report_path, root), "json": rel_str(result.json_path, root), "changelog": rel_str(result.changelog_path, root), "status": result.status, "applied_count": result.applied_count}

    @router.get("/workflow/runs/{run_id}")
    def workflow_state(run_id: str, project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        state_path = run_state_path(root, run_id)
        if not state_path.exists():
            raise HTTPException(status_code=404, detail=f"workflow run not found: {run_id}")
        return json.loads(state_path.read_text(encoding="utf-8"))

    @router.get("/workflow/artifact")
    def workflow_artifact(project_root: str, path: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        artifact = safe_relative_path(root, path)
        if not artifact.exists() or not artifact.is_file():
            raise HTTPException(status_code=404, detail=f"artifact not found: {path}")
        text = artifact.read_text(encoding="utf-8")
        return {"path": rel_str(artifact, root), "json": json.loads(text)} if artifact.suffix.lower() == ".json" else {"path": rel_str(artifact, root), "content": text}

    @router.post("/workflow/approve")
    def workflow_approve(payload: ApprovalRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = record_workflow_approval(root, payload.run_id, payload.decision, actor=payload.actor, notes=payload.notes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "approval_path": rel_str(result.approval_path, root), "index_path": rel_str(result.index_path, root), "task_path": rel_str(result.task_path, root) if result.task_path else ""}

    return router


def run_response(result, root: Path) -> dict[str, object]:
    return {"run_id": result.run_id, "status": result.status, "state_path": rel_str(result.state_path, root), "log_path": rel_str(result.log_path, root), "nodes": result.node_count, "blocked": result.blocked}


def dashboard_response(payload: dict[str, object], root: Path) -> dict[str, object]:
    frontend = payload.get("frontend") if isinstance(payload.get("frontend"), dict) else {}
    return {"ok": True, "project_root": str(root), "dashboard": payload, "summary": payload.get("summary", {}), "route_audits": payload.get("route_audits", []), "next_actions": payload.get("next_actions", []), "recent_events": payload.get("recent_events", []), "paths": {"markdown": "workflow/dashboard/workflow_dashboard.md", "json": str(frontend.get("json") or "workflow/dashboard/workflow_dashboard.json"), "html": str(frontend.get("html") or "workflow/dashboard/workflow_dashboard.html")}, "rules": payload.get("rules", [])}
