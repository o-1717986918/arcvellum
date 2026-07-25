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
from ..common import call_handler, project_root as resolve_project_root
from ..models import (
    StyleAuthorCreateRequest,
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
    authoring: StyleAuthoringService


def build_style_lab_router(deps: StyleLabRouterDependencies) -> APIRouter:
    router = APIRouter()
    _register_authoring_routes(router, deps)

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
