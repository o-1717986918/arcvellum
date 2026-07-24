"""Project library location, project registration, and direction-history routes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..common import call_handler, project_root as resolve_project_root
from ..models import DirectionRequest, ProjectCreateRequest, ProjectLocationRequest, ProjectOpenRequest, ProjectsRootRequest


@dataclass(frozen=True)
class ProjectRouterDependencies:
    config: dict[str, Any]
    default_projects_root: Callable[[], Path]
    save_config: Callable[[dict[str, Any]], None]
    list_projects: Callable[[], dict[str, Any]]
    current_project: Callable[[], dict[str, Any]]
    register_project: Callable[[str], dict[str, Any]]
    validate_project_location: Callable[..., dict[str, Any]]
    create_project: Callable[..., dict[str, Any]]
    read_directions: Callable[[Path, int], list[dict[str, Any]]]
    record_direction: Callable[[Path, str], dict[str, Any]]


def _payload_values(payload: Any) -> dict[str, Any]:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def build_project_router(deps: ProjectRouterDependencies) -> APIRouter:
    """Build project-management routes without leaking filesystem policy into app assembly."""

    router = APIRouter()

    @router.get("/projects")
    def projects_index():
        return {"ok": True, **deps.list_projects()}

    @router.get("/projects/current")
    def projects_current():
        return deps.current_project()

    @router.get("/projects/default-location")
    def projects_default_location():
        application = deps.config.get("application") if isinstance(deps.config.get("application"), dict) else {}
        root = Path(str(application.get("projects_root") or deps.default_projects_root())).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return {
            "ok": True,
            "projects_root": str(root),
            "source": str(application.get("projects_root_source") or "platform-default"),
            "portable_mode": bool(application.get("portable_mode", False)),
        }

    @router.put("/projects/default-location")
    def projects_default_location_update(payload: ProjectsRootRequest):
        root = Path(payload.projects_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir() or not os.access(root, os.W_OK):
            raise HTTPException(status_code=400, detail="默认作品库必须是可写入的文件夹。")
        application = deps.config.setdefault("application", {})
        application["projects_root"] = str(root)
        application["projects_root_source"] = "user-selected"
        deps.save_config(deps.config)
        return {"ok": True, "projects_root": str(root), "source": "user-selected", "affects_existing_projects": False}

    @router.post("/projects/open")
    def projects_open(payload: ProjectOpenRequest):
        return call_handler(lambda: {"ok": True, "project": deps.register_project(payload.project_root)})

    @router.post("/projects/validate-location")
    def projects_validate_location(payload: ProjectLocationRequest):
        return call_handler(lambda: {"ok": True, **deps.validate_project_location(**_payload_values(payload))})

    @router.post("/projects/create")
    def projects_create(payload: ProjectCreateRequest):
        return call_handler(lambda: {"ok": True, "project": deps.create_project(**_payload_values(payload))})

    @router.get("/projects/directions")
    def projects_directions(project_root: str, limit: int = 20):
        root = resolve_project_root(project_root)
        return {"ok": True, "items": deps.read_directions(root, limit=limit)}

    @router.post("/projects/directions")
    def projects_record_direction(payload: DirectionRequest):
        return call_handler(lambda: deps.record_direction(resolve_project_root(payload.project_root), payload.message))

    return router
