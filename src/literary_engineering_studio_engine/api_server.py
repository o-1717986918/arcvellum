"""Compatibility facade for the legacy Engine FastAPI adapter.

The Studio product owns the modern application API.  This legacy surface is
kept for existing Dify and workflow clients, but its request contracts,
security rules and endpoint families now live under :mod:`.api`.
"""

from __future__ import annotations

from pathlib import Path

from . import __version__
from .api.common import (
    ensure_target_allowed as _ensure_target_allowed,
    frontend_file as _frontend_file,
    is_relative_to as _is_relative_to,
    read_text as _read_text,
    rel_str as _rel_str,
    reject_bypass as _reject_bypass,
    require_api_token as _require_api_token,
    root_policy as _root_policy,
    run_state_path as _run_state_path,
    safe_agent_run_dir as _safe_agent_run_dir,
    safe_project_root as _safe_project_root,
    safe_relative_path as _safe_relative_path,
    tail_jsonl as _tail_jsonl,
)
from .api.models import (
    ApprovalRequest,
    AssetCreateRequest,
    AssetPromoteRequest,
    AssetReviewRequest,
    AssistantChatRequest,
    CanonApplyRequest,
    DemoProjectRequest,
    DirectorChatRequest,
    DisplayFieldRequest,
    HumanChoiceRequest,
    InitProjectRequest,
    RunAgentRequest,
    RunWorkflowRequest,
    SaveConfigRequest,
    StyleAuthorRequest,
    StyleCompileRequest,
    StyleEvalRequest,
    StyleMountRequest,
    StyleSkillBuildRequest,
    StyleSourceImportRequest,
    StyleWorkRequest,
    UiNoteRequest,
)
from .api.routers.agents import (
    director_conversation as _director_conversation,
    director_response as _director_response,
    handle_assistant_message as _handle_assistant_message,
    message_requests_new_project as _message_requests_new_project,
    resolve_director_root as _resolve_director_root,
)
from .api.routers.application import merge_profiles_preserving_api_keys as _merge_profiles_preserving_api_keys
from .api.routers.application import build_application_router
from .api.routers.agents import build_agent_router
from .api.routers.assets import build_asset_router
from .api.routers.projects import build_project_router, project_summary_payload as _project_summary
from .api.routers.style_lab import build_style_lab_router, safe_stamp as _safe_stamp, style_library_path as _style_library_path
from .api.routers.workflow import build_workflow_router, run_response as _run_response

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover - optional HTTP dependency
    FastAPI = None


def create_app(allowed_roots: list[str | Path] | None = None, api_token: str = ""):
    """Build the legacy Engine API without duplicating Studio runtime concerns."""
    if FastAPI is None:
        raise RuntimeError("FastAPI backend requires optional deps: fastapi, uvicorn, pydantic")
    root_policy = _root_policy(allowed_roots)
    token = api_token.strip()
    app = FastAPI(title="Literary Engineering Workbench API", version=__version__)
    app.include_router(build_application_router(version=__version__, api_token=token, allowed_roots=root_policy))
    app.include_router(build_style_lab_router(api_token=token, allowed_roots=root_policy))
    app.include_router(build_project_router(api_token=token, allowed_roots=root_policy))
    app.include_router(build_workflow_router(api_token=token, allowed_roots=root_policy))
    app.include_router(build_asset_router(api_token=token, allowed_roots=root_policy))
    app.include_router(build_agent_router(api_token=token, allowed_roots=root_policy))
    return app
