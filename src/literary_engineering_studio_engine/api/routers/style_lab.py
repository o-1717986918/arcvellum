"""Style-library endpoints for the legacy Engine API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ...platform_agent_tasks import write_platform_style_prompt_eval_task
from ...style_lab import (
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
from ..common import rel_str, reject_bypass, require_api_token, safe_project_root
from ..models import (
    StyleAuthorRequest,
    StyleCompileRequest,
    StyleEvalRequest,
    StyleMountRequest,
    StyleSkillBuildRequest,
    StyleSourceImportRequest,
    StyleWorkRequest,
)

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    HTTPException = None
    Request = object


def build_style_lab_router(*, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.get("/style-lab/library")
    def style_lab_library(http_request: Request, style_library_root: str = ""):
        require_api_token(http_request, api_token)
        library = ensure_style_library(style_library_path(style_library_root))
        return {
            "ok": True,
            "style_library_root": str(library),
            "default_style_library_root": str(default_style_library_root()),
            "authors": list_author_projects(library),
            "style_skills": list_style_skills(library),
        }

    @router.post("/style-lab/author")
    def style_lab_author(payload: StyleAuthorRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            result = create_author_project(
                style_library_path(payload.style_library_root),
                name=payload.name,
                author_id=payload.author_id,
                mode=payload.mode,
                source_note=payload.source_note,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "style_library_root": str(result.library_root), "author_id": result.author_id, "author_dir": rel_str(result.author_dir, result.library_root), "manifest": rel_str(result.manifest_path, result.library_root)}

    @router.post("/style-lab/work")
    def style_lab_work(payload: StyleWorkRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            result = create_author_work(style_library_path(payload.style_library_root), author_id=payload.author_id, title=payload.title, work_id=payload.work_id, year=payload.year, notes=payload.notes)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "style_library_root": str(result.library_root), "author_id": result.author_id, "work_id": result.work_id, "work_dir": rel_str(result.work_dir, result.library_root), "manifest": rel_str(result.manifest_path, result.library_root)}

    @router.post("/style-lab/import-source")
    def style_lab_import_source(payload: StyleSourceImportRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            result = import_work_source(style_library_path(payload.style_library_root), author_id=payload.author_id, work_id=payload.work_id, text=payload.text, filename=payload.filename, chunk_chars=payload.chunk_chars)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "style_library_root": str(result.library_root), "author_id": result.author_id, "work_id": result.work_id, "source_id": result.source_id, "raw": rel_str(result.raw_path, result.library_root), "normalized": rel_str(result.normalized_path, result.library_root), "manifest": rel_str(result.manifest_path, result.library_root), "chunk_count": result.chunk_count, "char_count": result.char_count}

    @router.post("/style-lab/compile")
    def style_lab_compile(payload: StyleCompileRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            result = run_author_style_learning_platform_task(style_library_path(payload.style_library_root), author_id=payload.author_id, profile_id=payload.profile_id)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "status": "pending_platform_agent", "receiver": "platform-agent", "style_library_root": str(result.library_root), "author_id": result.author_id, "profile_id": result.profile_id, "profile_dir": rel_str(result.profile_dir, result.library_root), "profile": rel_str(result.profile_path, result.library_root), "metrics": rel_str(result.metrics_path, result.library_root), "style_prompt_task": rel_str(result.style_prompt_task_path, result.library_root), "expected_style_prompt": rel_str(result.expected_style_prompt_path, result.library_root), "expected_json": rel_str(result.expected_json_path, result.library_root), "style_prompt": rel_str(result.expected_style_prompt_path, result.library_root), "source_count": result.source_count}

    @router.post("/style-lab/build-skill")
    def style_lab_build_skill(payload: StyleSkillBuildRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            result = build_style_skill(style_library_path(payload.style_library_root), author_id=payload.author_id, profile_id=payload.profile_id, style_id=payload.style_id)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "style_library_root": str(result.library_root), "author_id": result.author_id, "profile_id": result.profile_id, "style_id": result.style_id, "skill_dir": rel_str(result.skill_dir, result.library_root), "manifest": rel_str(result.manifest_path, result.library_root), "style_markdown": rel_str(result.style_markdown_path, result.library_root), "prompt": rel_str(result.prompt_path, result.library_root)}

    @router.post("/style-lab/evaluate")
    def style_lab_evaluate(payload: StyleEvalRequest, http_request: Request):
        require_api_token(http_request, api_token)
        try:
            library = ensure_style_library(style_library_path(payload.style_library_root))
            profile_dir = library / "authors" / payload.author_id / "profiles" / payload.profile_id
            if not profile_dir.exists():
                raise FileNotFoundError(f"profile dir not found: {profile_dir}")
            input_dir = profile_dir / "evaluation_inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            stamp = safe_stamp()
            reference = input_dir / f"{stamp}-reference.txt"
            task_input = input_dir / f"{stamp}-input.txt"
            reference.write_text(payload.reference_text.strip() + "\n", encoding="utf-8")
            task_input.write_text(payload.task_input_text.strip() + "\n", encoding="utf-8")
            result = write_platform_style_prompt_eval_task(profile_dir, reference=reference, task_input=task_input, mode=payload.mode)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "status": "pending_platform_agent", "receiver": "platform-agent", "style_library_root": str(library), "style_prompt_eval_task": rel_str(result.task_path, library), "expected_candidate": rel_str(result.expected_report_path, library), "expected_prompt_manifest": rel_str(result.expected_json_path, library), "reference": rel_str(reference, library), "task_input": rel_str(task_input, library), "mode": payload.mode}

    @router.post("/style-lab/mount")
    def style_lab_mount(payload: StyleMountRequest, http_request: Request):
        require_api_token(http_request, api_token)
        reject_bypass(payload, "POST /style-lab/mount")
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = mount_style_skill(root, library_root=style_library_path(payload.style_library_root), style_id=payload.style_id, allow_unreviewed=payload.allow_unreviewed)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "project_root": str(result.project_root), "style_id": result.style_id, "mount_dir": rel_str(result.mount_dir, root), "mount_manifest": rel_str(result.mount_manifest_path, root), "project_style": rel_str(result.project_style_path, root), "active_style_skill": active_project_style(root)}

    @router.get("/style-lab/mounts")
    def style_lab_mounts(project_root: str, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        return {"ok": True, "project_root": str(root), "active_style_skill": active_project_style(root)}

    return router


def style_library_path(value: str) -> Path | None:
    text = str(value or "").strip()
    return Path(text).expanduser().resolve() if text else None


def safe_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
