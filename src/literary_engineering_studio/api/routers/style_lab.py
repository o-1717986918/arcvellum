"""Mounted style-skill library routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ...application.style.transactions import (
    StyleAuthoringService,
    StyleIdentityConflictError,
    StyleSourceDuplicateError,
    StyleTransactionError,
)
from ...application.style.task_service import (
    StyleBuildIntentError,
    StyleTaskService,
)
from literary_engineering_studio_engine.literary.style.session import (
    StyleSessionConflictError,
    StyleSessionError,
)
from ..common import call_handler, project_root as resolve_project_root
from ..models import (
    StyleAuthorCreateRequest,
    StyleBuildRequest,
    StyleCompileRequest,
    StyleMountRequest,
    StyleSourceCreateRequest,
    StyleWorkCreateRequest,
)


@dataclass(frozen=True)
class StyleLabRouterDependencies:
    config: dict[str, Any]
    style_library: Callable[[dict[str, Any], str], dict[str, Any]]
    style_mounts: Callable[[dict[str, Any], Path], dict[str, Any]]
    mount_style: Callable[[dict[str, Any], Path, str, str], dict[str, Any]]
    style_authors: Callable[[Path | None], dict[str, object]]
    style_versions: Callable[[Path | None, Path | None], dict[str, object]]
    style_version_detail: Callable[[Path, str, str], dict[str, object]]
    authoring: StyleAuthoringService
    tasks: StyleTaskService


def build_style_lab_router(deps: StyleLabRouterDependencies) -> APIRouter:
    router = APIRouter()
    _register_authoring_routes(router, deps)
    _register_engineering_routes(router, deps)

    @router.get("/style-lab/library")
    def style_lab_library(style_library_root: str = ""):
        return call_handler(lambda: deps.style_library(deps.config, style_library_root))

    @router.get("/style-lab/authors")
    def style_lab_authors(style_library_root: str = ""):
        return call_handler(lambda: deps.style_authors(_optional_path(style_library_root)))

    @router.get("/style-lab/versions")
    def style_lab_versions(style_library_root: str = "", project_root: str = ""):
        return call_handler(
            lambda: deps.style_versions(
                _optional_path(style_library_root),
                resolve_project_root(project_root) if project_root else None,
            )
        )

    @router.get("/style-lab/versions/{style_id}/{version_id}")
    def style_lab_version_detail(
        style_id: str,
        version_id: str,
        project_root: str,
    ):
        return call_handler(
            lambda: deps.style_version_detail(
                resolve_project_root(project_root),
                style_id,
                version_id,
            )
        )

    @router.get("/style-lab/mounts")
    def style_lab_mounts(project_root: str):
        return call_handler(lambda: deps.style_mounts(deps.config, resolve_project_root(project_root)))

    @router.post("/style-lab/mount")
    def style_lab_mount(payload: StyleMountRequest):
        return call_handler(
            lambda: deps.mount_style(
                deps.config,
                resolve_project_root(payload.project_root),
                payload.style_library_root,
                payload.style_id,
            )
        )

    return router


def _register_engineering_routes(
    router: APIRouter,
    deps: StyleLabRouterDependencies,
) -> None:
    @router.post("/style-lab/compile")
    def style_lab_compile(payload: StyleCompileRequest):
        try:
            result = deps.tasks.compile(
                resolve_project_root(payload.project_root),
                _optional_path(payload.style_library_root),
                author_id=payload.author_id,
                profile_id=payload.profile_id,
                display_name=payload.display_name,
                training_sources=[
                    item.model_dump() if hasattr(item, "model_dump") else item.dict()
                    for item in payload.training_sources
                ],
                holdout_sources=[
                    item.model_dump() if hasattr(item, "model_dump") else item.dict()
                    for item in payload.holdout_sources
                ],
                runtime=payload.runtime,
            )
            return {"ok": True, **result}
        except StyleSessionError as exc:
            raise _style_session_error(exc) from exc

    @router.post("/style-lab/build")
    def style_lab_build(payload: StyleBuildRequest):
        try:
            return {
                "ok": True,
                **deps.tasks.build(
                    resolve_project_root(payload.project_root),
                    author_id=payload.author_id,
                    profile_id=payload.profile_id,
                    runtime=payload.runtime,
                ),
            }
        except StyleBuildIntentError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": exc.code,
                    "stage": exc.stage,
                    "message": str(exc),
                },
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "style_profile_not_found",
                    "message": str(exc),
                },
            ) from exc
        except StyleSessionError as exc:
            raise _style_session_error(exc) from exc

def _register_authoring_routes(router: APIRouter, deps: StyleLabRouterDependencies) -> None:
    @router.post("/style-lab/authors")
    def style_lab_create_author(payload: StyleAuthorCreateRequest):
        try:
            return {
                "ok": True,
                **deps.authoring.create_author(
                    _optional_path(payload.style_library_root),
                    author_id=payload.author_id,
                    name=payload.name,
                    rights_mode=payload.rights_mode,
                    rights_declaration=payload.rights_declaration,
                ),
            }
        except StyleTransactionError as exc:
            raise _transaction_error(exc) from exc

    @router.post("/style-lab/works")
    def style_lab_create_work(payload: StyleWorkCreateRequest):
        try:
            return {
                "ok": True,
                **deps.authoring.create_work(
                    _optional_path(payload.style_library_root),
                    author_id=payload.author_id,
                    work_id=payload.work_id,
                    title=payload.title,
                    year=payload.year,
                    notes=payload.notes,
                ),
            }
        except (FileNotFoundError, StyleTransactionError) as exc:
            raise _transaction_error(exc) from exc

    @router.post("/style-lab/sources")
    def style_lab_import_source(payload: StyleSourceCreateRequest):
        try:
            return {
                "ok": True,
                **deps.authoring.import_source(
                    _optional_path(payload.style_library_root),
                    author_id=payload.author_id,
                    work_id=payload.work_id,
                    filename=payload.filename,
                    media_type=payload.media_type,
                    content=payload.content,
                    rights_mode=payload.rights_mode,
                    rights_declaration=payload.rights_declaration,
                ),
            }
        except (FileNotFoundError, StyleTransactionError) as exc:
            raise _transaction_error(exc) from exc


def _optional_path(value: str) -> Path | None:
    return Path(value).expanduser().resolve() if value.strip() else None


def _transaction_error(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "style_transaction_invalid")
    status = 409 if isinstance(exc, (StyleIdentityConflictError, StyleSourceDuplicateError)) else 400
    details: dict[str, object] = {"code": code, "message": str(exc)}
    if isinstance(exc, StyleSourceDuplicateError):
        details["existing"] = exc.existing
    return HTTPException(status_code=status, detail=details)


def _style_session_error(exc: StyleSessionError) -> HTTPException:
    status = 409 if isinstance(exc, StyleSessionConflictError) else 400
    return HTTPException(
        status_code=status,
        detail={
            "code": getattr(exc, "code", "style_session_invalid"),
            "message": str(exc),
        },
    )
