"""Formal delivery-center read model and safe artifact download routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..common import call_handler, project_root as resolve_project_root


@dataclass(frozen=True)
class DeliveryRouterDependencies:
    delivery_snapshot: Callable[[Path], dict[str, Any]]
    resolve_delivery_file: Callable[[Path, str], Path]
    delivery_content_type: Callable[[Path], str]
    stream_read_model: Callable[[str, Callable[[], dict[str, Any]], float, int], Any]


def build_delivery_router(deps: DeliveryRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/project/delivery")
    def project_delivery(project_root: str):
        root = resolve_project_root(project_root)
        return call_handler(lambda: deps.delivery_snapshot(root))

    @router.get("/project/delivery/stream")
    def project_delivery_stream(project_root: str, interval_seconds: float = 5.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        return deps.stream_read_model("delivery", lambda: deps.delivery_snapshot(root), interval_seconds, max_events)

    @router.get("/project/delivery/download")
    def project_delivery_download(project_root: str, path: str):
        root = resolve_project_root(project_root)
        try:
            target = deps.resolve_delivery_file(root, path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FileResponse(target, media_type=deps.delivery_content_type(target), filename=target.name)

    return router
