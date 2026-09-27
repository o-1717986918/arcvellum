"""HTTP surface for the layered prompt workbench."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...application.prompt_workbench import PromptWorkbenchService
from ..common import call_handler, project_root as resolve_project_root


class PromptEditRequest(BaseModel):
    scope: str
    project_root: str = ""
    text: str = Field(min_length=1, max_length=12000)
    expected_digest: str = ""


class PromptActivationRequest(BaseModel):
    scope: str
    project_root: str = ""
    version: int = Field(ge=1)
    expected_digest: str = ""


class PromptResetRequest(BaseModel):
    scope: str
    project_root: str = ""
    expected_digest: str = ""


class PromptPreviewRequest(BaseModel):
    project_root: str = ""
    layer_ids: list[str] = Field(min_length=1, max_length=24)


def build_prompts_router(workbench: PromptWorkbenchService) -> APIRouter:
    router = APIRouter()

    @router.get("/prompts/catalog")
    def catalog(project_root: str = ""):
        return call_handler(lambda: workbench.catalog(_root(project_root)))

    @router.get("/prompts/layers/{layer_id}/history")
    def history(layer_id: str, scope: str, project_root: str = ""):
        return call_handler(lambda: workbench.history(layer_id, scope=scope, project_root=_root(project_root)))

    @router.put("/prompts/layers/{layer_id}")
    def save(layer_id: str, payload: PromptEditRequest):
        return call_handler(lambda: workbench.save(layer_id, payload.text, scope=payload.scope,
                                                   project_root=_root(payload.project_root),
                                                   expected_digest=payload.expected_digest))

    @router.post("/prompts/layers/{layer_id}/activate")
    def activate(layer_id: str, payload: PromptActivationRequest):
        return call_handler(lambda: workbench.activate(layer_id, payload.version, scope=payload.scope,
                                                       project_root=_root(payload.project_root),
                                                       expected_digest=payload.expected_digest))

    @router.post("/prompts/layers/{layer_id}/reset")
    def reset(layer_id: str, payload: PromptResetRequest):
        return call_handler(lambda: workbench.reset(layer_id, scope=payload.scope,
                                                    project_root=_root(payload.project_root),
                                                    expected_digest=payload.expected_digest))

    @router.post("/prompts/preview")
    def preview(payload: PromptPreviewRequest):
        return call_handler(lambda: workbench.snapshot(tuple(payload.layer_ids), _root(payload.project_root)))

    return router


def _root(value: str) -> Path | None:
    return resolve_project_root(value) if value else None
