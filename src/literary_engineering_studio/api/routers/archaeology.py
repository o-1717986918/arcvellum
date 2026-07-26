"""Project Archaeology import and read-model routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException

from ...application.archaeology import ArchaeologyImportSpec
from ..common import call_handler, project_root as resolve_project_root
from ..models import ArchaeologyImportRequest


@dataclass(frozen=True)
class ArchaeologyRouterDependencies:
    options: Callable[[], dict[str, object]]
    catalog: Callable[..., dict[str, object]]
    workbench: Callable[..., dict[str, object]]
    import_source: Callable[..., dict[str, object]]


def build_archaeology_router(deps: ArchaeologyRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/archaeology/options")
    def archaeology_options():
        return {"ok": True, **deps.options()}

    @router.get("/archaeology/imports")
    def archaeology_imports(project_root: str):
        return call_handler(
            lambda: {
                "ok": True,
                **deps.catalog(resolve_project_root(project_root)),
            }
        )

    @router.get("/archaeology/workbench/{work_id}")
    def archaeology_workbench(work_id: str, project_root: str):
        try:
            return {
                "ok": True,
                **deps.workbench(resolve_project_root(project_root), work_id),
            }
        except FileNotFoundError as exc:
            raise _archaeology_error(404, "archaeology_import_not_found", exc) from exc
        except ValueError as exc:
            raise _archaeology_error(400, "archaeology_import_invalid", exc) from exc

    @router.post("/archaeology/imports")
    def archaeology_import(payload: ArchaeologyImportRequest):
        try:
            spec = ArchaeologyImportSpec.create(
                filename=payload.filename,
                text=payload.text,
                content_base64=payload.content_base64,
                title=payload.title,
                work_id=payload.work_id,
                mode=payload.mode,
                rights_declaration=payload.rights_declaration,
                chunk_size=payload.chunk_size,
                overwrite=payload.overwrite,
            )
            return {
                "ok": True,
                **deps.import_source(
                    resolve_project_root(payload.project_root),
                    spec,
                ),
            }
        except FileExistsError as exc:
            raise _archaeology_error(409, "archaeology_import_exists", exc) from exc
        except FileNotFoundError as exc:
            raise _archaeology_error(404, "archaeology_project_not_found", exc) from exc
        except ValueError as exc:
            raise _archaeology_error(400, "archaeology_import_invalid", exc) from exc

    return router


def _archaeology_error(status: int, code: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": str(exc)},
    )
