"""FastAPI adapter for Dify and external workflow clients."""

import json
import re
import secrets
import time
from pathlib import Path

from . import __version__
from .agent_provider import run_agent_task
from .asset_workshop import create_asset_candidate, list_asset_candidates, promote_candidate_asset, review_candidate_asset
from .canon_evolver import apply_canon_patch, build_canon_patch_backlog
from .demo_project import build_demo_project
from .director_agent import (
    DirectorBootstrapResult,
    bootstrap_project_from_direction,
    build_director_status,
    director_project_slug,
    run_director_turn,
)
from .init_project import InitOptions, init_work_project
from .approval import record_workflow_approval
from .formal_mode import FormalModeBypassError, ensure_no_bypass
from .model_config import as_env_exports, config_path, default_config, load_config, redacted_effective_config, save_config
from .project_interaction import (
    build_current_human_choices,
    build_editable_schema,
    record_human_choice,
    record_ui_note,
    save_display_field,
)
from .project_library import build_project_library, find_project_library_item
from .workflow_activity import build_task_package_summary, build_workflow_activity
from .style_lab import (
    active_project_style,
    build_style_skill,
    create_author_project,
    create_author_work,
    default_style_library_root,
    ensure_style_library,
    import_work_source,
    list_author_projects,
    list_style_skills,
    mount_style_skill,
    run_author_style_learning_platform_task,
)
from .platform_agent_tasks import write_platform_style_prompt_eval_task
from .workflow_dashboard import build_workflow_dashboard
from .workflow_runner import run_workflow

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, Response, StreamingResponse
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - exercised when optional deps are absent
    FastAPI = None
    HTTPException = None
    Request = object
    HTMLResponse = None
    Response = None
    StreamingResponse = None
    BaseModel = object


class RunWorkflowRequest(BaseModel):
    project_root: str
    mode: str = "full-cycle"
    scene: str = "scenes/scene_0001.yaml"
    chapter_id: str = "chapter_0001"
    target_length: int = 100000
    include_blocked: bool = False
    overwrite_draft: bool = False
    generate_candidate: bool = False
    promote_candidate: bool = False
    agent_review: bool = False
    agent_tasks: bool = False
    provider: str = "auto"
    run_id: str = ""
    resume_run_id: str = ""
    overwrite_run: bool = False


class ApprovalRequest(BaseModel):
    project_root: str
    run_id: str
    decision: str
    actor: str = "human"
    notes: str = ""


class DisplayFieldRequest(BaseModel):
    project_root: str
    target_type: str
    target_id: str
    field: str
    value: object = ""
    actor: str = "user-ui"


class UiNoteRequest(BaseModel):
    project_root: str
    target_type: str
    target_id: str
    note: str
    actor: str = "user-ui"


class HumanChoiceRequest(BaseModel):
    project_root: str
    choice_id: str = ""
    route: str = ""
    task_id: str = ""
    decision_type: str = "general_project_choice"
    target: dict = {}
    options: list = []
    selected: str
    rationale: str = ""
    actor: str = "user-ui"
    materialize: bool = True


class RunAgentRequest(BaseModel):
    project_root: str
    agent_id: str
    task: str
    system_prompt: str
    user_prompt: str
    provider: str = "auto"
    out_dir: str = ""


class SaveConfigRequest(BaseModel):
    active_profile: str = "deepseek"
    profiles: dict = {}
    defaults: dict = {}


class InitProjectRequest(BaseModel):
    target: str
    title: str
    premise: str = ""
    genre: str = ""
    work_type: str = "novel"
    target_length: int = 30000
    language: str = "zh-CN"


class DemoProjectRequest(BaseModel):
    target: str
    title: str = "文学工程 Demo"
    run_agent_workflow: bool = True


class AssistantChatRequest(BaseModel):
    project_root: str = ""
    message: str


class DirectorChatRequest(BaseModel):
    project_root: str = ""
    message: str
    provider: str = "auto"
    auto_execute: bool = True
    agent_tasks: bool = False
    create_project_if_missing: bool = True
    project_parent: str = ""
    project_title: str = ""


class AssetCreateRequest(BaseModel):
    project_root: str
    asset_type: str = "character"
    brief: str = ""
    target_id: str = ""
    source: str = ""
    provider: str = "auto"


class AssetReviewRequest(BaseModel):
    project_root: str
    candidate: str
    provider: str = "auto"


class AssetPromoteRequest(BaseModel):
    project_root: str
    candidate: str
    group: str = ""
    approval_run_id: str = ""
    allow_unapproved: bool = False


class CanonApplyRequest(BaseModel):
    project_root: str
    patch: str = ""
    approval_run_id: str = ""
    allow_unapproved: bool = False


class StyleAuthorRequest(BaseModel):
    style_library_root: str = ""
    name: str
    author_id: str = ""
    mode: str = "public_domain_or_authorized"
    source_note: str = ""


class StyleWorkRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    title: str
    work_id: str = ""
    year: str = ""
    notes: str = ""


class StyleSourceImportRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    work_id: str
    text: str
    filename: str = ""
    chunk_chars: int = 4000


class StyleCompileRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    provider: str = "auto"


class StyleSkillBuildRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    style_id: str = ""


class StyleEvalRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    profile_id: str = "default"
    reference_text: str
    task_input_text: str
    mode: str = "back-translation"
    provider: str = "auto"


class StyleMountRequest(BaseModel):
    project_root: str
    style_library_root: str = ""
    style_id: str
    allow_unreviewed: bool = False


def create_app(allowed_roots: list[str | Path] | None = None, api_token: str = ""):
    if FastAPI is None:
        raise RuntimeError("FastAPI backend requires optional deps: fastapi, uvicorn, pydantic")

    root_policy = _root_policy(allowed_roots)
    token = api_token.strip()
    app = FastAPI(title="Literary Engineering Workbench API", version=__version__)

    @app.get("/", response_class=HTMLResponse)
    def ui_root():
        return _frontend_file("index.html", "text/html; charset=utf-8")

    @app.get("/ui/{path:path}")
    def ui_asset(path: str):
        suffix = Path(path).suffix.lower()
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".svg": "image/svg+xml; charset=utf-8",
        }.get(suffix, "text/plain; charset=utf-8")
        return _frontend_file(path, content_type)

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "version": __version__,
            "auth_required": bool(token),
            "allowed_roots": [str(root) for root in root_policy],
        }

    @app.get("/config")
    def get_config(http_request: Request):
        _require_api_token(http_request, token)
        return redacted_effective_config()

    @app.post("/config")
    def update_config(payload: SaveConfigRequest, http_request: Request):
        _require_api_token(http_request, token)
        existing = load_config()
        existing["active_profile"] = payload.active_profile
        existing["profiles"] = _merge_profiles_preserving_api_keys(existing.get("profiles", {}), payload.profiles)
        existing["defaults"] = payload.defaults or existing.get("defaults", {})
        path = save_config(existing)
        return {"ok": True, "config_path": str(path), "effective": redacted_effective_config()}

    @app.post("/config/default")
    def write_default_config(http_request: Request):
        _require_api_token(http_request, token)
        path = save_config(default_config())
        return {"ok": True, "config_path": str(path), "effective": redacted_effective_config()}

    @app.get("/config/env")
    def config_env(http_request: Request):
        _require_api_token(http_request, token)
        return {"config_path": str(config_path()), "exports": as_env_exports()}

    @app.get("/style-lab/library")
    def style_lab_library(http_request: Request, style_library_root: str = ""):
        _require_api_token(http_request, token)
        library = ensure_style_library(_style_library_path(style_library_root))
        return {
            "ok": True,
            "style_library_root": str(library),
            "default_style_library_root": str(default_style_library_root()),
            "authors": list_author_projects(library),
            "style_skills": list_style_skills(library),
        }

    @app.post("/style-lab/author")
    def style_lab_author(payload: StyleAuthorRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            result = create_author_project(
                _style_library_path(payload.style_library_root),
                name=payload.name,
                author_id=payload.author_id,
                mode=payload.mode,
                source_note=payload.source_note,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "style_library_root": str(result.library_root),
            "author_id": result.author_id,
            "author_dir": _rel_str(result.author_dir, result.library_root),
            "manifest": _rel_str(result.manifest_path, result.library_root),
        }

    @app.post("/style-lab/work")
    def style_lab_work(payload: StyleWorkRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            result = create_author_work(
                _style_library_path(payload.style_library_root),
                author_id=payload.author_id,
                title=payload.title,
                work_id=payload.work_id,
                year=payload.year,
                notes=payload.notes,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "style_library_root": str(result.library_root),
            "author_id": result.author_id,
            "work_id": result.work_id,
            "work_dir": _rel_str(result.work_dir, result.library_root),
            "manifest": _rel_str(result.manifest_path, result.library_root),
        }

    @app.post("/style-lab/import-source")
    def style_lab_import_source(payload: StyleSourceImportRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            result = import_work_source(
                _style_library_path(payload.style_library_root),
                author_id=payload.author_id,
                work_id=payload.work_id,
                text=payload.text,
                filename=payload.filename,
                chunk_chars=payload.chunk_chars,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "style_library_root": str(result.library_root),
            "author_id": result.author_id,
            "work_id": result.work_id,
            "source_id": result.source_id,
            "raw": _rel_str(result.raw_path, result.library_root),
            "normalized": _rel_str(result.normalized_path, result.library_root),
            "manifest": _rel_str(result.manifest_path, result.library_root),
            "chunk_count": result.chunk_count,
            "char_count": result.char_count,
        }

    @app.post("/style-lab/compile")
    def style_lab_compile(payload: StyleCompileRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            result = run_author_style_learning_platform_task(
                _style_library_path(payload.style_library_root),
                author_id=payload.author_id,
                profile_id=payload.profile_id,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "status": "pending_platform_agent",
            "receiver": "platform-agent",
            "style_library_root": str(result.library_root),
            "author_id": result.author_id,
            "profile_id": result.profile_id,
            "profile_dir": _rel_str(result.profile_dir, result.library_root),
            "profile": _rel_str(result.profile_path, result.library_root),
            "metrics": _rel_str(result.metrics_path, result.library_root),
            "style_prompt_task": _rel_str(result.style_prompt_task_path, result.library_root),
            "expected_style_prompt": _rel_str(result.expected_style_prompt_path, result.library_root),
            "expected_json": _rel_str(result.expected_json_path, result.library_root),
            "style_prompt": _rel_str(result.expected_style_prompt_path, result.library_root),
            "source_count": result.source_count,
        }

    @app.post("/style-lab/build-skill")
    def style_lab_build_skill(payload: StyleSkillBuildRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            result = build_style_skill(
                _style_library_path(payload.style_library_root),
                author_id=payload.author_id,
                profile_id=payload.profile_id,
                style_id=payload.style_id,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "style_library_root": str(result.library_root),
            "author_id": result.author_id,
            "profile_id": result.profile_id,
            "style_id": result.style_id,
            "skill_dir": _rel_str(result.skill_dir, result.library_root),
            "manifest": _rel_str(result.manifest_path, result.library_root),
            "style_markdown": _rel_str(result.style_markdown_path, result.library_root),
            "prompt": _rel_str(result.prompt_path, result.library_root),
        }

    @app.post("/style-lab/evaluate")
    def style_lab_evaluate(payload: StyleEvalRequest, http_request: Request):
        _require_api_token(http_request, token)
        try:
            library = ensure_style_library(_style_library_path(payload.style_library_root))
            profile_dir = library / "authors" / payload.author_id / "profiles" / payload.profile_id
            if not profile_dir.exists():
                raise FileNotFoundError(f"profile dir not found: {profile_dir}")
            input_dir = profile_dir / "evaluation_inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            stamp = _safe_stamp()
            reference = input_dir / f"{stamp}-reference.txt"
            task_input = input_dir / f"{stamp}-input.txt"
            reference.write_text(payload.reference_text.strip() + "\n", encoding="utf-8")
            task_input.write_text(payload.task_input_text.strip() + "\n", encoding="utf-8")
            result = write_platform_style_prompt_eval_task(
                profile_dir,
                reference=reference,
                task_input=task_input,
                mode=payload.mode,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "status": "pending_platform_agent",
            "receiver": "platform-agent",
            "style_library_root": str(library),
            "style_prompt_eval_task": _rel_str(result.task_path, library),
            "expected_candidate": _rel_str(result.expected_report_path, library),
            "expected_prompt_manifest": _rel_str(result.expected_json_path, library),
            "reference": _rel_str(reference, library),
            "task_input": _rel_str(task_input, library),
            "mode": payload.mode,
        }

    @app.post("/style-lab/mount")
    def style_lab_mount(payload: StyleMountRequest, http_request: Request):
        _require_api_token(http_request, token)
        _reject_bypass(payload, "POST /style-lab/mount")
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = mount_style_skill(
                root,
                library_root=_style_library_path(payload.style_library_root),
                style_id=payload.style_id,
                allow_unreviewed=payload.allow_unreviewed,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "project_root": str(result.project_root),
            "style_id": result.style_id,
            "mount_dir": _rel_str(result.mount_dir, root),
            "mount_manifest": _rel_str(result.mount_manifest_path, root),
            "project_style": _rel_str(result.project_style_path, root),
            "active_style_skill": active_project_style(root),
        }

    @app.get("/style-lab/mounts")
    def style_lab_mounts(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        return {"ok": True, "project_root": str(root), "active_style_skill": active_project_style(root)}

    @app.get("/project/summary")
    def project_summary(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        return _project_summary(root)

    @app.get("/project/library")
    def project_library(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            return {"ok": True, **build_project_library(root)}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/project/library/item")
    def project_library_item(project_root: str, kind: str, item_id: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            return find_project_library_item(root, kind, item_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/project/library/stream")
    def project_library_stream(
        project_root: str,
        http_request: Request,
        interval_seconds: float = 6.0,
        max_events: int = 0,
    ):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
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

    @app.get("/project/editable-schema")
    def project_editable_schema(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        return {"ok": True, **build_editable_schema(root)}

    @app.patch("/project/display-field")
    def project_display_field(payload: DisplayFieldRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            return save_display_field(
                root,
                target_type=payload.target_type,
                target_id=payload.target_id,
                field=payload.field,
                value=payload.value,
                actor=payload.actor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/project/ui-note")
    def project_ui_note(payload: UiNoteRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            return record_ui_note(
                root,
                target_type=payload.target_type,
                target_id=payload.target_id,
                note=payload.note,
                actor=payload.actor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/project/init")
    def project_init(payload: InitProjectRequest, http_request: Request):
        _require_api_token(http_request, token)
        target = Path(payload.target).resolve()
        _ensure_target_allowed(target, root_policy)
        try:
            result = init_work_project(
                InitOptions(
                    target=target,
                    title=payload.title,
                    premise=payload.premise,
                    genre=payload.genre,
                    work_type=payload.work_type,
                    target_length=payload.target_length,
                    language=payload.language,
                )
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "root": str(result.root), "files": [file.relative_to(result.root).as_posix() for file in result.files]}

    @app.post("/project/demo")
    def project_demo(payload: DemoProjectRequest, http_request: Request):
        _require_api_token(http_request, token)
        target = Path(payload.target).resolve()
        _ensure_target_allowed(target, root_policy)
        try:
            result = build_demo_project(target, title=payload.title, run_agent_workflow=payload.run_agent_workflow)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "ok": True,
            "root": str(result.root),
            "report": _rel_str(result.report_path, result.root),
            "workflow_state": _rel_str(result.workflow_state, result.root) if result.workflow_state else "",
        }

    @app.post("/workflow/run")
    def workflow_run(payload: RunWorkflowRequest, http_request: Request):
        _require_api_token(http_request, token)
        _reject_bypass(payload, "POST /workflow/run")
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = run_workflow(
                root,
                mode=payload.mode,
                scene=Path(payload.scene),
                chapter_id=payload.chapter_id,
                target_length=payload.target_length,
                include_blocked=payload.include_blocked,
                overwrite_draft=payload.overwrite_draft,
                generate_candidate=payload.generate_candidate,
                promote_candidate=payload.promote_candidate,
                agent_review=payload.agent_review,
                agent_tasks=payload.agent_tasks,
                provider=payload.provider,
                run_id=payload.run_id or None,
                resumed_from=payload.resume_run_id,
                overwrite_run=payload.overwrite_run,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _run_response(result, root)

    @app.get("/workflow/dashboard")
    def workflow_dashboard(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            result = build_workflow_dashboard(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "ok": True,
            "project_root": str(root),
            "dashboard": payload,
            "summary": payload.get("summary", {}),
            "route_audits": payload.get("route_audits", []),
            "next_actions": payload.get("next_actions", []),
            "recent_events": payload.get("recent_events", []),
            "paths": {
                "markdown": _rel_str(result.markdown_path, root),
                "json": _rel_str(result.json_path, root),
                "html": _rel_str(result.html_path, root),
            },
            "rules": payload.get("rules", []),
        }

    @app.get("/workflow/dashboard/stream")
    def workflow_dashboard_stream(
        project_root: str,
        http_request: Request,
        interval_seconds: float = 8.0,
        max_events: int = 0,
    ):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        interval = max(3.0, min(60.0, float(interval_seconds or 8.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            while True:
                result = build_workflow_dashboard(root)
                payload = json.loads(result.json_path.read_text(encoding="utf-8"))
                data = {
                    "ok": True,
                    "project_root": str(root),
                    "dashboard": payload,
                    "summary": payload.get("summary", {}),
                    "route_audits": payload.get("route_audits", []),
                    "next_actions": payload.get("next_actions", []),
                    "recent_events": payload.get("recent_events", []),
                    "paths": {
                        "markdown": _rel_str(result.markdown_path, root),
                        "json": _rel_str(result.json_path, root),
                        "html": _rel_str(result.html_path, root),
                    },
                    "rules": payload.get("rules", []),
                }
                yield "event: dashboard\n"
                yield "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/workflow/activity")
    def workflow_activity(project_root: str, http_request: Request, limit: int = 30):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            return {"ok": True, **build_workflow_activity(root, limit=max(1, min(200, int(limit or 30))))}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/workflow/activity/stream")
    def workflow_activity_stream(
        project_root: str,
        http_request: Request,
        interval_seconds: float = 4.0,
        max_events: int = 0,
    ):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        interval = max(2.0, min(60.0, float(interval_seconds or 4.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            sent = 0
            while True:
                payload = {"ok": True, **build_workflow_activity(root)}
                yield "event: activity\n"
                yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/workflow/task-package")
    def workflow_task_package(project_root: str, task_id: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            return {"ok": True, **build_task_package_summary(root, task_id)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/workflow/current-choice")
    def workflow_current_choice(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            return {"ok": True, **build_current_human_choices(root)}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/workflow/human-choice")
    def workflow_human_choice(payload: HumanChoiceRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            return record_human_choice(root, payload.model_dump() if hasattr(payload, "model_dump") else payload.dict())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/canon/backlog")
    def canon_backlog(project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            result = build_canon_patch_backlog(root)
            payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "project_root": str(root),
            "summary": payload.get("summary", {}),
            "items": payload.get("items", []),
            "paths": {
                "markdown": _rel_str(result.output_path, root),
                "json": _rel_str(result.json_path, root),
            },
        }

    @app.post("/canon/apply")
    def canon_apply(payload: CanonApplyRequest, http_request: Request):
        _require_api_token(http_request, token)
        _reject_bypass(payload, "POST /canon/apply")
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = apply_canon_patch(
                root,
                patch=Path(payload.patch) if payload.patch else None,
                approval_run_id=payload.approval_run_id,
                allow_unapproved=payload.allow_unapproved,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "project_root": str(root),
            "patch": _rel_str(result.patch_path, root),
            "report": _rel_str(result.report_path, root),
            "json": _rel_str(result.json_path, root),
            "changelog": _rel_str(result.changelog_path, root),
            "status": result.status,
            "applied_count": result.applied_count,
        }

    @app.post("/agent/run")
    def agent_run(payload: RunAgentRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = run_agent_task(
                root,
                agent_id=payload.agent_id,
                task=payload.task,
                system_prompt=payload.system_prompt,
                user_prompt=payload.user_prompt,
                provider=payload.provider,
                output_dir=Path(payload.out_dir) if payload.out_dir else None,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "run_id": result.run_id,
            "status": result.status,
            "parse_status": result.parse_status,
            "run_dir": _rel_str(result.run_dir, root),
            "input": _rel_str(result.input_path, root),
            "raw_output": _rel_str(result.raw_output_path, root),
            "parsed_output": _rel_str(result.parsed_output_path, root),
            "validation": _rel_str(result.validation_path, root),
        }

    @app.get("/agent/runs/{run_id}")
    def agent_run_state(run_id: str, project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        run_dir = _safe_agent_run_dir(root, run_id)
        parsed_path = run_dir / "parsed_output.json"
        validation_path = run_dir / "validation_report.md"
        if not parsed_path.exists():
            raise HTTPException(status_code=404, detail=f"agent run not found: {run_id}")
        return {
            "run_id": run_id,
            "run_dir": _rel_str(run_dir, root),
            "parsed_output": json.loads(parsed_path.read_text(encoding="utf-8")),
            "validation_report": validation_path.read_text(encoding="utf-8") if validation_path.exists() else "",
        }

    @app.post("/assistant/chat")
    def assistant_chat(payload: AssistantChatRequest, http_request: Request):
        _require_api_token(http_request, token)
        message = payload.message.strip()
        project_root_value = payload.project_root.strip()
        root = _safe_project_root(project_root_value, root_policy) if project_root_value else None
        try:
            result = _handle_assistant_message(message, root)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    @app.post("/director/chat")
    def director_chat(payload: DirectorChatRequest, http_request: Request):
        _require_api_token(http_request, token)
        root, bootstrap = _resolve_director_root(payload, root_policy)
        try:
            result = run_director_turn(
                root,
                payload.message,
                provider=payload.provider,
                auto_execute=payload.auto_execute,
                agent_tasks=payload.agent_tasks,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if bootstrap:
            result.decision["project_created"] = True
            result.decision["project_title"] = bootstrap.title
            result.decision["project_bootstrap"] = _rel_str(bootstrap.bootstrap_path, root)
            result.artifacts["project_bootstrap"] = _rel_str(bootstrap.bootstrap_path, root)
        return _director_response(result, root, bootstrap=bootstrap)

    @app.get("/director/status")
    def director_status(project_root: str, http_request: Request, limit: int = 8):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        return build_director_status(root, limit=limit)

    @app.post("/asset/create")
    def asset_create(payload: AssetCreateRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = create_asset_candidate(
                root,
                asset_type=payload.asset_type,
                brief=payload.brief,
                target_id=payload.target_id,
                source=Path(payload.source) if payload.source else None,
                provider=payload.provider,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "asset_type": result.asset_type,
            "candidate_id": result.candidate_id,
            "candidate": _rel_str(result.candidate_path, root),
            "report": _rel_str(result.report_path, root),
            "run_dir": _rel_str(result.run_dir, root),
            "validation": _rel_str(result.validation_path, root),
            "status": result.status,
        }

    @app.post("/asset/create-character")
    def asset_create_character(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "character"
        return asset_create(payload, http_request)

    @app.post("/asset/create-world")
    def asset_create_world(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "world"
        return asset_create(payload, http_request)

    @app.post("/asset/create-outline")
    def asset_create_outline(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "outline"
        return asset_create(payload, http_request)

    @app.get("/asset/candidates")
    def asset_candidates(project_root: str, http_request: Request, asset_type: str = ""):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        try:
            items = list_asset_candidates(root, asset_type=asset_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"items": items, "count": len(items)}

    @app.post("/asset/review")
    def asset_review(payload: AssetReviewRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = review_candidate_asset(root, payload.candidate, provider=payload.provider)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "candidate": _rel_str(result.candidate_path, root),
            "report": _rel_str(result.report_path, root),
            "json": _rel_str(result.json_path, root),
            "agent_run": _rel_str(result.agent_run_dir, root),
            "status": result.status,
            "errors": result.error_count,
            "warnings": result.warning_count,
        }

    @app.post("/asset/promote")
    def asset_promote(payload: AssetPromoteRequest, http_request: Request):
        _require_api_token(http_request, token)
        _reject_bypass(payload, "POST /asset/promote")
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = promote_candidate_asset(
                root,
                payload.candidate,
                group=payload.group,
                approval_run_id=payload.approval_run_id,
                allow_unapproved=payload.allow_unapproved,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "candidate": _rel_str(result.candidate_path, root),
            "manifest": _rel_str(result.manifest_path, root),
            "report": _rel_str(result.report_path, root),
            "outputs": [_rel_str(path, root) for path in result.output_paths],
            "status": result.status,
        }

    @app.get("/workflow/runs/{run_id}")
    def workflow_state(run_id: str, project_root: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        state_path = _run_state_path(root, run_id)
        if not state_path.exists():
            raise HTTPException(status_code=404, detail=f"workflow run not found: {run_id}")
        return json.loads(state_path.read_text(encoding="utf-8"))

    @app.get("/workflow/artifact")
    def workflow_artifact(project_root: str, path: str, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(project_root, root_policy)
        artifact = _safe_relative_path(root, path)
        if not artifact.exists() or not artifact.is_file():
            raise HTTPException(status_code=404, detail=f"artifact not found: {path}")
        text = artifact.read_text(encoding="utf-8")
        if artifact.suffix.lower() == ".json":
            return {"path": _rel_str(artifact, root), "json": json.loads(text)}
        return {"path": _rel_str(artifact, root), "content": text}

    @app.post("/workflow/approve")
    def workflow_approve(payload: ApprovalRequest, http_request: Request):
        _require_api_token(http_request, token)
        root = _safe_project_root(payload.project_root, root_policy)
        try:
            result = record_workflow_approval(
                root,
                payload.run_id,
                payload.decision,
                actor=payload.actor,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "approval_path": _rel_str(result.approval_path, root),
            "index_path": _rel_str(result.index_path, root),
            "task_path": _rel_str(result.task_path, root) if result.task_path else "",
        }

    return app


def _root_policy(allowed_roots: list[str | Path] | None) -> list[Path]:
    if not allowed_roots:
        return []
    return [Path(root).resolve() for root in allowed_roots]


def _safe_project_root(project_root: str | Path, allowed_roots: list[Path]) -> Path:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"project root not found: {root}")
    if allowed_roots and not any(_is_relative_to(root, allowed) for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"project root is outside allowed roots: {root}")
    return root


def _ensure_target_allowed(target: Path, allowed_roots: list[Path]) -> None:
    parent = target.parent.resolve()
    if allowed_roots and not any(_is_relative_to(parent, allowed) or parent == allowed for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"target is outside allowed roots: {target}")


def _resolve_director_root(payload: DirectorChatRequest, allowed_roots: list[Path]) -> tuple[Path, DirectorBootstrapResult | None]:
    requested = payload.project_root.strip()
    message = payload.message.strip()
    wants_new = _message_requests_new_project(message)
    if requested:
        requested_path = Path(requested).resolve()
        if requested_path.is_dir() and not wants_new:
            return _safe_project_root(requested_path, allowed_roots), None
        if requested_path.exists() and not requested_path.is_dir():
            raise HTTPException(status_code=400, detail=f"project root is not a directory: {requested_path}")
        if not payload.create_project_if_missing and not wants_new:
            return _safe_project_root(requested_path, allowed_roots), None
        target = requested_path if not requested_path.exists() else _unique_director_project_target(requested_path.parent, message, payload.project_title)
        _ensure_target_allowed(target, allowed_roots)
        bootstrap = _bootstrap_director_project(target, payload)
        _remember_default_project_root(bootstrap.root)
        return bootstrap.root, bootstrap

    configured = str(load_config().get("defaults", {}).get("project_root", "") or "").strip()
    if configured and Path(configured).resolve().is_dir() and not wants_new:
        return _safe_project_root(configured, allowed_roots), None

    if not payload.create_project_if_missing:
        raise HTTPException(status_code=400, detail="project_root is required when create_project_if_missing is false")
    base = _director_project_parent(payload.project_parent, allowed_roots)
    target = _unique_director_project_target(base, message, payload.project_title)
    _ensure_target_allowed(target, allowed_roots)
    bootstrap = _bootstrap_director_project(target, payload)
    _remember_default_project_root(bootstrap.root)
    return bootstrap.root, bootstrap


def _director_project_parent(project_parent: str, allowed_roots: list[Path]) -> Path:
    if project_parent.strip():
        parent = Path(project_parent).resolve()
    elif allowed_roots:
        parent = allowed_roots[0] / "director-projects"
    else:
        parent = Path.cwd() / "director-projects"
    if allowed_roots and not any(_is_relative_to(parent, allowed) or parent == allowed for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"project parent is outside allowed roots: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _unique_director_project_target(base: Path, message: str, title: str = "") -> Path:
    slug_source = title.strip() or message.strip() or "literary-project"
    slug = director_project_slug(slug_source)
    target = (base / slug).resolve()
    if not target.exists():
        return target
    for index in range(2, 1000):
        candidate = (base / f"{slug}-{index}").resolve()
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=409, detail=f"could not allocate project target under: {base}")


def _bootstrap_director_project(target: Path, payload: DirectorChatRequest) -> DirectorBootstrapResult:
    try:
        return bootstrap_project_from_direction(
            target,
            payload.message,
            title=payload.project_title,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _message_requests_new_project(message: str) -> bool:
    text = message.lower()
    tokens = [
        "新建项目",
        "创建项目",
        "创建一个项目",
        "新项目",
        "完整文学项目",
        "生成一个完整",
        "一句话生成",
        "start a new project",
        "create a new project",
    ]
    return any(token in text for token in tokens)


def _remember_default_project_root(root: Path) -> None:
    config = load_config()
    defaults = dict(config.get("defaults", {}) if isinstance(config.get("defaults", {}), dict) else {})
    defaults["project_root"] = str(root)
    config["defaults"] = defaults
    save_config(config)


def _safe_relative_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise HTTPException(status_code=400, detail="artifact path must be relative")
    resolved = (root / path).resolve()
    if not _is_relative_to(resolved, root):
        raise HTTPException(status_code=403, detail="artifact path escapes project root")
    return resolved


def _style_library_path(value: str) -> Path | None:
    text = str(value or "").strip()
    return Path(text).expanduser().resolve() if text else None


def _safe_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _project_summary(root: Path) -> dict[str, object]:
    workflow_index = root / "workflow" / "runs" / "index.jsonl"
    approval_index = root / "workflow" / "approvals" / "index.jsonl"
    recent_runs = _tail_jsonl(workflow_index, 8)
    return {
        "root": str(root),
        "project_yaml": _read_text(root / "project.yaml", 4000),
        "has_project": (root / "project.yaml").exists(),
        "counts": {
            "characters": len(list((root / "characters").glob("*.yaml"))) if (root / "characters").exists() else 0,
            "scenes": len(list((root / "scenes").glob("*.yaml"))) if (root / "scenes").exists() else 0,
            "drafts": len(list((root / "drafts" / "scenes").glob("*.md"))) if (root / "drafts" / "scenes").exists() else 0,
            "agent_runs": len(list((root / "agents" / "runs").iterdir())) if (root / "agents" / "runs").exists() else 0,
        },
        "paths": {
            "agents": str(root / "agents"),
            "reviews": str(root / "reviews"),
            "workflow_runs": str(root / "workflow" / "runs"),
            "config": str(config_path()),
        },
        "active_style_skill": active_project_style(root),
        "recent_runs": recent_runs,
        "approval_records": len(_tail_jsonl(approval_index, 1000)),
    }


def _merge_profiles_preserving_api_keys(existing: object, incoming: object) -> dict[str, object]:
    current = existing if isinstance(existing, dict) else {}
    updates = incoming if isinstance(incoming, dict) else {}
    if not updates:
        return dict(current)
    merged = dict(current)
    for name, profile in updates.items():
        if not isinstance(profile, dict):
            merged[name] = profile
            continue
        previous = current.get(name, {}) if isinstance(current.get(name, {}), dict) else {}
        item = dict(previous)
        item.update(profile)
        if not str(profile.get("api_key", "") or "").strip():
            previous_key = str(previous.get("api_key", "") or "").strip()
            if previous_key:
                item["api_key"] = previous_key
            else:
                item.pop("api_key", None)
        item.pop("api_key_set", None)
        merged[name] = item
    return merged


def _handle_assistant_message(message: str, root: Path | None) -> dict[str, object]:
    lowered = message.lower()
    if any(token in lowered for token in ["测试模型", "连接", "connection", "api test"]):
        if root is None:
            raise ValueError("project_root is required for model connection test")
        result = run_agent_task(
            root,
            agent_id="ui-connection-test",
            task="connection-test",
            system_prompt="You are a connection test assistant.",
            user_prompt="请只回复：模型连接成功。",
            provider="http-chat",
        )
        return {"reply": "已发起模型连接测试。", "action": "agent-run", "data": {"run_id": result.run_id, "parsed_output": _rel_str(result.parsed_output_path, root)}}
    if any(token in lowered for token in ["配置", "config", "provider", "模型", "deepseek"]):
        return {"reply": "已读取当前全局配置。密钥可来自环境变量，也可来自本机全局配置中保存的 profile api_key。", "action": "config", "data": redacted_effective_config()}
    if root is None:
        raise ValueError("project_root is required for project actions")
    result = run_director_turn(root, message, provider="auto", auto_execute=True)
    return _director_response(result, root)


def _frontend_file(path: str, content_type: str):
    if "/" in path or "\\" in path:
        clean = Path(path)
        if any(part == ".." for part in clean.parts):
            raise HTTPException(status_code=400, detail="invalid frontend path")
    frontend_root = Path(__file__).resolve().parents[2] / "frontend"
    target = (frontend_root / path).resolve()
    if not _is_relative_to(target, frontend_root) or not target.is_file():
        raise HTTPException(status_code=404, detail=f"frontend asset not found: {path}")
    if content_type.startswith("image/") and "svg" not in content_type:
        return Response(content=target.read_bytes(), media_type=content_type)
    return Response(content=target.read_text(encoding="utf-8"), media_type=content_type)


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _read_text(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")[:limit]


def _run_state_path(root: Path, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run_id")
    return _safe_relative_path(root, Path("workflow") / "runs" / run_id / "workflow_state.json")


def _safe_agent_run_dir(root: Path, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run_id")
    return _safe_relative_path(root, Path("agents") / "runs" / run_id)


def _require_api_token(request: Request, api_token: str) -> None:
    if not api_token:
        return
    authorization = request.headers.get("authorization", "")
    bearer_token = ""
    if authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
    header_token = request.headers.get("x-lew-api-token", "").strip()
    if not (
        (bearer_token and secrets.compare_digest(bearer_token, api_token))
        or (header_token and secrets.compare_digest(header_token, api_token))
    ):
        raise HTTPException(status_code=401, detail="missing or invalid API token")


def _reject_bypass(payload: object, surface: str) -> None:
    try:
        ensure_no_bypass(payload, surface=surface)
    except FormalModeBypassError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _record_approval(root: Path, run_id: str, decision: str, actor: str = "human", notes: str = "") -> Path:
    return record_workflow_approval(root, run_id, decision, actor=actor, notes=notes).approval_path


def _run_response(result, root: Path) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "state_path": _rel_str(result.state_path, root),
        "log_path": _rel_str(result.log_path, root),
        "nodes": result.node_count,
        "blocked": result.blocked,
    }


def _director_response(result, root: Path, *, bootstrap: DirectorBootstrapResult | None = None) -> dict[str, object]:
    conversation = _director_conversation(result, root)
    return {
        "reply": result.reply,
        "action": result.action,
        "conversation": conversation,
        "data": {
            "project_root": str(root),
            "project_created": bool(bootstrap),
            "project_title": bootstrap.title if bootstrap else str(result.decision.get("project_title") or ""),
            "project_bootstrap": _rel_str(bootstrap.bootstrap_path, root) if bootstrap else str(result.decision.get("project_bootstrap") or ""),
            "run_id": result.run_id,
            "status": result.status,
            "decision": _rel_str(result.decision_path, root),
            "report": _rel_str(result.report_path, root),
            "agent_run": _rel_str(result.agent_run_dir, root),
            "validation": _rel_str(result.validation_path, root),
            "workflow_state": _rel_str(result.workflow_state_path, root) if result.workflow_state_path else "",
            "tool_loop": str(result.decision.get("tool_loop") or result.artifacts.get("tool_loop") or ""),
            "artifacts": result.artifacts,
            "decision_payload": result.decision,
        },
    }


def _director_conversation(result, root: Path) -> dict[str, object]:
    decision = result.decision
    artifacts = getattr(result, "artifacts", {}) if isinstance(getattr(result, "artifacts", {}), dict) else {}
    workflow = str(decision.get("chosen_workflow") or "none")
    label = _workflow_label(workflow)
    custom_headline = _safe_conversation_text(decision.get("conversation_headline"), limit=80)
    custom_message = _safe_conversation_text(decision.get("conversation_reply"), limit=700)
    if custom_headline:
        headline = custom_headline
    elif bool(decision.get("project_created")):
        headline = f"我已经为你建立「{decision.get('project_title') or '新文学项目'}」"
    elif result.status == "failed":
        headline = "我接住了你的方向，但后台执行遇到阻塞"
    elif workflow == "none":
        headline = "我先帮你看项目状态"
    elif bool(decision.get("auto_execute")):
        headline = f"我已把方向推进到「{label}」"
    else:
        headline = f"我建议下一步先做「{label}」"
    if custom_message:
        message = custom_message
    elif bool(decision.get("project_created")):
        message = "我已经把这句话整理成可持续维护的文学工程项目，并会从设定、人物、主线和后续任务开始推进。"
    elif result.status == "failed":
        message = "这轮方向我已经接住了。接下来我会先处理阻塞点，再把真正影响创作走向的选择带回来给你。"
    elif workflow == "none":
        message = "这一轮我不会改动项目。你可以继续告诉我想强化的题材气质、人物压力或剧情方向。"
    elif bool(decision.get("auto_execute")):
        message = "我会沿着这个方向继续推进；你只需要判断人物压力、题材气质和剧情节奏是否符合预期。"
    else:
        message = "我会把你的大方向转成下一轮创作推进。你只需要继续用自然语言确认、修正或追加偏好。"
    return {
        "speaker": "创作总监",
        "headline": headline,
        "message": message,
        "next_questions": _director_next_questions(decision, workflow),
        "will_handle": _director_will_handle(workflow, decision),
        "audit": {
            "run_id": result.run_id,
            "status": result.status,
            "workflow": workflow,
            "provider": str(decision.get("provider") or ""),
            "project_root": str(root),
            "report": _rel_str(result.report_path, root),
            "validation": _rel_str(result.validation_path, root),
            "workflow_state": _rel_str(result.workflow_state_path, root) if result.workflow_state_path else "",
            "tool_loop": str(decision.get("tool_loop") or artifacts.get("tool_loop") or ""),
        },
    }


def _workflow_label(workflow: str) -> str:
    labels = {
        "none": "项目状态确认",
        "project-seeding": "项目孵化",
        "character-lab": "人物与关系梳理",
        "worldbuilding-lab": "世界观与场域梳理",
        "outline-lab": "主线与章节规划",
        "scene-loop": "场景推进与审查",
    }
    return labels.get(workflow, workflow or "项目状态确认")


def _director_next_questions(decision: dict[str, object], workflow: str) -> list[str]:
    raw_items = _visible_list(decision.get("user_visible_decisions"), limit=4)
    polished = [_strip_list_marker(item) for item in raw_items if _is_safe_user_facing_item(item)]
    if polished:
        return polished[:3]
    if str(decision.get("intent") or "") == "conversation":
        return [
            "你可以继续补充题材气质、人物口味、叙事禁忌或节奏偏好。",
            "也可以直接说继续，我会按已记录的方向推进后台创作。",
        ]
    defaults = {
        "project-seeding": [
            "这部作品下一步更想先强化题材气质、人物压力，还是主线结构？",
            "也可以直接说继续，我会先把方向整理成一版可讨论的初步方案。",
        ],
        "character-lab": [
            "人物部分你更想先压住主角困境、对手动机，还是关系冲突？",
            "也可以只给一句感觉，我来把背景故事和行为逻辑补齐。",
        ],
        "worldbuilding-lab": [
            "世界观更偏现实冷硬、超常悬疑，还是组织和制度压力更强？",
            "你只需要确认氛围方向，其余规则我会在后台推演。",
        ],
        "outline-lab": [
            "主线更想先确定结局方向、阶段反转，还是人物长期代价？",
            "也可以说继续，我会把大方向拆成章节推进方案。",
        ],
        "scene-loop": [
            "下一场更想推进冲突、揭示信息，还是强化人物选择？",
            "如果没有新偏好，我会沿当前方向继续推进并自检。",
        ],
        "none": [
            "你可以继续告诉我想强化的题材气质、人物重心或剧情方向。",
        ],
    }
    return defaults.get(workflow, defaults["none"])


def _director_will_handle(workflow: str, decision: dict[str, object] | None = None) -> list[str]:
    decision = decision or {}
    if str(decision.get("intent") or "") == "conversation":
        return ["把这轮偏好写入创作总监记忆。", "后续调度人物、剧情、文风和审查时优先参考这些方向。"]
    label = _workflow_label(workflow)
    if workflow != "none":
        tools = _visible_director_tools(workflow)
        if tools:
            return tools
    if workflow == "none":
        return ["读取项目状态和最近记录。", "把需要你关注的创作方向整理成简短回复。"]
    return [
        f"把你的创作方向拆给「{label}」相关节点处理。",
        "让生成、审查和取舍记录在后台完成。",
        "只把真正需要你判断的创作方向带回对话里。",
    ]


def _is_safe_user_facing_item(item: str) -> bool:
    text = item.strip()
    if not text or not re.search(r"[\u4e00-\u9fff]", text):
        return False
    lowered = text.lower()
    blocked = [
        "approve",
        "reject",
        "candidate",
        "schema",
        "workflow",
        "run_",
        "json",
        "yaml",
        "canon",
        "agent",
        "候选",
        "审批",
        "批准",
        "拒绝",
        "工作流",
        "校验",
        "审计",
        "文件",
        "路径",
    ]
    return not any(token in lowered for token in blocked)


def _safe_conversation_text(value: object, *, limit: int) -> str:
    text = str(value or "").strip()
    if not text or not re.search(r"[\u4e00-\u9fff]", text):
        return ""
    blocked = ["decision_payload", "project_yaml", "schema", "workflow", "run_", "yaml", "json", "approve", "reject"]
    lowered = text.lower()
    if any(token in lowered for token in blocked):
        return ""
    return text[:limit]


def _visible_director_tools(workflow: str) -> list[str]:
    if workflow == "project-seeding":
        return ["建立或补齐作品骨架。", "整理世界观、人物和主线的第一批候选方向。", "把后续需要你判断的创作取舍带回对话里。"]
    if workflow == "character-lab":
        return ["梳理人物困境、隐性背景故事和关系压力。", "检查人物行为是否能支撑后续剧情。", "把真正影响走向的关系选择带回对话里。"]
    if workflow == "worldbuilding-lab":
        return ["梳理世界规则、关键地点和组织压力。", "检查设定边界是否会限制或推动剧情。", "把需要你确认的氛围和规则取舍带回对话里。"]
    if workflow == "outline-lab":
        return ["整理主线结构、阶段反转和章节推进。", "检查人物代价与剧情节奏是否匹配。", "把关键走向选择带回对话里。"]
    if workflow == "scene-loop":
        return ["读取上下文并推进下一场创作。", "让角色推演、分支推演和审查在后台完成。", "把需要你判断的场景效果带回对话里。"]
    return []


def _strip_list_marker(item: str) -> str:
    return re.sub(r"^\s*[-*0-9.、)）]+", "", item).strip()


def _visible_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value[:limit] if str(item).strip()]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
