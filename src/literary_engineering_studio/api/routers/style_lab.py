"""Mounted style-skill library routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from ..common import call_handler, project_root as resolve_project_root
from ..models import StyleMountRequest


@dataclass(frozen=True)
class StyleLabRouterDependencies:
    config: dict[str, Any]
    style_library: Callable[[dict[str, Any], str], dict[str, Any]]
    style_mounts: Callable[[dict[str, Any], Path], dict[str, Any]]
    mount_style: Callable[[dict[str, Any], Path, str, str], dict[str, Any]]
    style_authors: Callable[[Path | None], dict[str, object]]
    style_versions: Callable[[Path | None, Path | None], dict[str, object]]


def build_style_lab_router(deps: StyleLabRouterDependencies) -> APIRouter:
    router = APIRouter()

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


def _optional_path(value: str) -> Path | None:
    return Path(value).expanduser().resolve() if value.strip() else None
