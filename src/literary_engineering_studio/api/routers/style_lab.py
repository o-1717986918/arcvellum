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


def build_style_lab_router(deps: StyleLabRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/style-lab/library")
    def style_lab_library(style_library_root: str = ""):
        return call_handler(lambda: deps.style_library(deps.config, style_library_root))

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
