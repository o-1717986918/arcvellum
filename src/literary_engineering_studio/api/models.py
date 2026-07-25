"""Pydantic request contracts for the local Studio HTTP API.

These are transport-only DTOs. They deliberately carry no route logic or
project I/O so routers can share the same public input schema without creating
an API-to-domain dependency cycle.
"""

from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - keeps the base package importable
    BaseModel = object


class WorkerRequest(BaseModel):
    project_root: str
    route: str = "scene-development"
    runtime: str = "opencode"
    task_id: str = ""
    scene: str = ""
    idempotency_key: str = ""


class StyleMountRequest(BaseModel):
    project_root: str
    style_library_root: str = ""
    style_id: str


class StyleAuthorCreateRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    name: str
    rights_mode: str
    rights_declaration: str


class StyleWorkCreateRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    work_id: str
    title: str
    year: str = ""
    notes: str = ""


class StyleSourceCreateRequest(BaseModel):
    style_library_root: str = ""
    author_id: str
    work_id: str
    filename: str
    media_type: str = "text/plain"
    content: str
    rights_mode: str
    rights_declaration: str


class ProjectCreateRequest(BaseModel):
    parent_directory: str = ""
    title: str
    folder_name: str = ""
    work_type: str = "novel"
    target_length: int = 30000
    premise: str = ""
    genre: str = ""


class ProjectOpenRequest(BaseModel):
    project_root: str


class ProjectLocationRequest(BaseModel):
    mode: str
    project_root: str = ""
    parent_directory: str = ""
    folder_name: str = ""


class ProjectsRootRequest(BaseModel):
    projects_root: str


class DirectionRequest(BaseModel):
    project_root: str
    message: str


class RunnerProbeRequest(BaseModel):
    model: str = ""
    role: str = "worker"
    timeout: int = 120


class OpenCodeCredentialRequest(BaseModel):
    provider_id: str
    credential: str


class CustomProviderModelRequest(BaseModel):
    id: str
    name: str = ""
    context: int = 0
    output: int = 0


class CustomProviderConnectionRequest(BaseModel):
    provider_id: str
    display_name: str
    base_url: str
    models: list[CustomProviderModelRequest]
    credential: str


class ModelSelectionRequest(BaseModel):
    model: str
    role: str = "all"


class AdvisorSessionRequest(BaseModel):
    project_root: str
    title: str = "项目问答"


class AdvisorQuestionRequest(BaseModel):
    question: str
    timeout: int = 180
    context: dict[str, Any] | None = None


class AdvisorPersonaSelectionRequest(BaseModel):
    project_root: str
    persona_id: str


class AdvisorCustomPersonaRequest(BaseModel):
    name: str
    tagline: str = ""
    prompt: str
    persona_id: str = ""


class AdvisorInboxReadRequest(BaseModel):
    read: bool = True


class AdvisorInboxSettingsRequest(BaseModel):
    project_root: str
    mode: str = "standard"
    quiet_start: str = "22:30"
    quiet_end: str = "08:00"


class ReaderPositionRequest(BaseModel):
    project_root: str
    unit_id: str
    scroll_ratio: float = 0.0


class ReaderBookmarkRequest(BaseModel):
    project_root: str
    unit_id: str
    enabled: bool = True


class AutopilotPolicyRequest(BaseModel):
    project_root: str
    policy: dict[str, Any]


class AutopilotStartRequest(BaseModel):
    project_root: str
    runtime: str = "opencode"
    authorized: bool = False


class AutopilotControlRequest(BaseModel):
    reason: str = "user-request"
    authorized: bool = False


class WritebackDecisionRequest(BaseModel):
    decision: str
    reason: str = ""


class WorkerRetryRequest(BaseModel):
    runtime: str = ""
    resume: bool = True


class CreativeQualityRequest(BaseModel):
    project_root: str
    profile: dict[str, Any]


class CreativeQualityPreviewRequest(BaseModel):
    project_root: str
    text: str
    profile: dict[str, Any] | None = None
    scope: str = ""


class RhythmPlanRequest(BaseModel):
    project_root: str
    entries: list[dict[str, Any]]
    book_profile: dict[str, Any] | None = None


class ArchiveAssetContentRequest(BaseModel):
    project_root: str
    content: str


class ArchiveStructuredContentRequest(ArchiveAssetContentRequest):
    pass


class ArchiveStructuredRenderRequest(ArchiveAssetContentRequest):
    source_revision: str
    fields: dict[str, Any]


class ArchiveAssetCommitRequest(BaseModel):
    project_root: str
    base_revision: str
    content: str
    semantic_review: str = "required"
    reason: str
    expected_impacts: list[str] = []


class ArchiveAssetCreatePreviewRequest(BaseModel):
    project_root: str
    asset_type: str
    local_id: str = ""
    content: str
    semantic_review: str = "required"
    reason: str
    expected_impacts: list[str] = []


class ArchiveAssetCreateCommitRequest(ArchiveAssetCreatePreviewRequest):
    preview_digest: str


class ArchiveRestorePreviewRequest(BaseModel):
    project_root: str
    revision: str
    reason: str


class ArchiveAssetArchiveRequest(BaseModel):
    project_root: str
    base_revision: str
    reason: str


class ArchiveAssetRestoreRequest(BaseModel):
    project_root: str
    entry_id: str
    reason: str


class ArchiveCandidatePromotionRequest(BaseModel):
    project_root: str
    preview_digest: str


__all__ = [
    "ArchiveAssetArchiveRequest",
    "ArchiveAssetCommitRequest",
    "ArchiveAssetContentRequest",
    "ArchiveAssetCreateCommitRequest",
    "ArchiveAssetCreatePreviewRequest",
    "ArchiveAssetRestoreRequest",
    "ArchiveCandidatePromotionRequest",
    "ArchiveRestorePreviewRequest",
    "ArchiveStructuredContentRequest",
    "ArchiveStructuredRenderRequest",
    "AdvisorCustomPersonaRequest",
    "AdvisorInboxReadRequest",
    "AdvisorInboxSettingsRequest",
    "AdvisorPersonaSelectionRequest",
    "AdvisorQuestionRequest",
    "AdvisorSessionRequest",
    "AutopilotControlRequest",
    "AutopilotPolicyRequest",
    "AutopilotStartRequest",
    "CreativeQualityPreviewRequest",
    "CreativeQualityRequest",
    "DirectionRequest",
    "ModelSelectionRequest",
    "OpenCodeCredentialRequest",
    "ProjectCreateRequest",
    "ProjectLocationRequest",
    "ProjectOpenRequest",
    "ProjectsRootRequest",
    "ReaderBookmarkRequest",
    "ReaderPositionRequest",
    "RhythmPlanRequest",
    "RunnerProbeRequest",
    "StyleMountRequest",
    "StyleAuthorCreateRequest",
    "StyleWorkCreateRequest",
    "StyleSourceCreateRequest",
    "WorkerRequest",
    "WorkerRetryRequest",
    "WritebackDecisionRequest",
]
