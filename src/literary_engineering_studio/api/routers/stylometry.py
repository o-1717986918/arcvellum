"""Experimental stylometry HTTP boundary over the project-scoped application service."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...application.style.stylometry_contracts import CorpusTextSource
from ...application.style.stylometry_service import StylometryService
from ..common import call_handler, project_root as resolve_root


class TextSourceRequest(BaseModel):
    source_id: str
    work_id: str
    text: str = Field(min_length=1, max_length=2_000_000)
    split: str = "train"
    topic: str = "unknown"
    genre: str = "narrative"
    markdown: bool = False


class StylometryAnalyzeRequest(BaseModel):
    project_root: str
    title: str = Field(min_length=1, max_length=80)
    sources: list[TextSourceRequest] = Field(min_length=1, max_length=64)


class StylometryParametersRequest(BaseModel):
    project_root: str
    profile_id: str
    dependency_json: str = Field(default="", max_length=16_000_000)


class StylometryCompileRequest(StylometryParametersRequest):
    controls_json: str = Field(max_length=128_000)
    title: str = Field(min_length=1, max_length=80)
    intent: str = Field(default="", max_length=8000)


class StylometrySaveRequest(StylometryCompileRequest):
    fragment_override: str | None = Field(default=None, max_length=32_000)


class StylometryMountRequest(BaseModel):
    project_root: str
    version_id: str = ""
    enabled: bool
    combine: str = "append"
    usage: str = "guide"
    expected_revision: int = Field(ge=0)


class StylometryMeasureRequest(BaseModel):
    project_root: str
    text: str = Field(min_length=1, max_length=2_000_000)
    version_id: str = ""
    candidate_json: str = Field(default="", max_length=16_000_000)


def build_stylometry_router(service: StylometryService):
    router = APIRouter(prefix="/stylometry", tags=["stylometry"])

    def invoke(method, payload, **extra):
        return call_handler(lambda: {"ok": True, **method(resolve_root(payload.project_root), **extra)})

    @router.get("/workbench")
    def workbench(project_root: str):
        return call_handler(lambda: {"ok": True, **service.workbench(resolve_root(project_root))})

    @router.post("/analyze")
    def analyze(payload: StylometryAnalyzeRequest):
        return invoke(service.analyze, payload, title=payload.title,
            sources=tuple(CorpusTextSource(**row.model_dump()) for row in payload.sources))

    @router.get("/profiles/{profile_id}")
    def profile(profile_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, **service.profile(resolve_root(project_root), profile_id)})

    @router.post("/parameters")
    def parameters(payload: StylometryParametersRequest):
        return invoke(service.parameters, payload, **_arguments(payload))

    @router.post("/compile")
    def compile_fragment(payload: StylometryCompileRequest):
        return invoke(service.compile, payload, **_arguments(payload))

    @router.post("/versions")
    def save_version(payload: StylometrySaveRequest):
        return invoke(service.save_version, payload, **_arguments(payload))

    @router.get("/versions/{version_id}")
    def version(version_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, **service.version(resolve_root(project_root), version_id)})

    @router.post("/mount")
    def mount(payload: StylometryMountRequest):
        return invoke(service.mount, payload, **_arguments(payload))

    @router.post("/measure")
    def measure(payload: StylometryMeasureRequest):
        return invoke(service.measure, payload, **_arguments(payload))

    return router


def _arguments(payload):
    return payload.model_dump(exclude={"project_root"})
