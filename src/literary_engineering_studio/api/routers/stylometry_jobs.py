"""Persistent analysis jobs over the application executor."""
from fastapi import APIRouter
from pydantic import BaseModel
from ...application.style.stylometry_contracts import CorpusTextSource
from ..common import call_handler, project_root as resolve_root
from .stylometry import StylometryAnalyzeRequest


class StylometryJobActionRequest(BaseModel):
    project_root: str


def build_stylometry_jobs_router(service):
    router = APIRouter(prefix="/stylometry/jobs", tags=["stylometry"])

    @router.get("")
    def list_jobs(project_root: str):
        return call_handler(lambda: {"ok": True, **service.list(resolve_root(project_root))})

    @router.post("")
    def launch(payload: StylometryAnalyzeRequest):
        return call_handler(lambda: {"ok": True, **service.launch(resolve_root(payload.project_root),
            tuple(CorpusTextSource(**row.model_dump()) for row in payload.sources), payload.title)})

    @router.get("/{job_id}")
    def read(job_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, **service.read(resolve_root(project_root), job_id)})

    @router.post("/{job_id}/cancel")
    def cancel(job_id: str, payload: StylometryJobActionRequest):
        return call_handler(lambda: {"ok": True, **service.cancel(resolve_root(payload.project_root), job_id)})

    @router.post("/{job_id}/resume")
    def resume(job_id: str, payload: StylometryJobActionRequest):
        return call_handler(lambda: {"ok": True, **service.resume(resolve_root(payload.project_root), job_id)})

    return router
