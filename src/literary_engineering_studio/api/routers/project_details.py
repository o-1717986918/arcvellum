"""Project detail projection and low-risk display/note interaction routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from ..common import call_handler, project_root as resolve_project_root


@dataclass(frozen=True)
class ProjectDetailRouterDependencies:
    config: dict[str, Any]
    build_dashboard: Callable[[dict[str, Any], Path], dict[str, Any]]
    build_reader_manifest: Callable[[Path], dict[str, Any]]
    public_reader_manifest: Callable[[dict[str, Any]], dict[str, Any]]
    load_creative_quality_profile: Callable[[Path], dict[str, Any]]
    save_display_field: Callable[[dict[str, Any], Path, dict[str, Any]], dict[str, Any]]
    record_ui_note: Callable[[dict[str, Any], Path, dict[str, Any]], dict[str, Any]]


def build_project_detail_router(deps: ProjectDetailRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/project/details")
    def project_details(project_root: str):
        root = resolve_project_root(project_root)
        dashboard = deps.build_dashboard(deps.config, root)
        reader = deps.public_reader_manifest(deps.build_reader_manifest(root))
        return {
            "ok": True,
            "schema": "arcvellum/project-details/v1",
            "project_root": str(root),
            "dashboard": dashboard,
            "reader": {
                "unit_count": len(reader.get("units", [])),
                "formal_chinese_chars": reader.get("total_chinese_content_chars", 0),
            },
            "creative_quality_profile": deps.load_creative_quality_profile(root),
        }

    @router.patch("/project/display-field")
    def project_display_field(payload: dict[str, Any]):
        return call_handler(lambda: deps.save_display_field(deps.config, resolve_project_root(str(payload.get("project_root") or "")), payload))

    @router.post("/project/ui-note")
    def project_ui_note(payload: dict[str, Any]):
        return call_handler(lambda: deps.record_ui_note(deps.config, resolve_project_root(str(payload.get("project_root") or "")), payload))

    return router
