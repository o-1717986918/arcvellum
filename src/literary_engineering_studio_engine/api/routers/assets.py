"""Candidate asset endpoints for the legacy Engine API."""

from __future__ import annotations

from pathlib import Path

from ...asset_workshop import create_asset_candidate, list_asset_candidates, promote_candidate_asset, review_candidate_asset
from ..common import rel_str, reject_bypass, require_api_token, safe_project_root
from ..models import AssetCreateRequest, AssetPromoteRequest, AssetReviewRequest

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    HTTPException = None
    Request = object


def build_asset_router(*, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.post("/asset/create")
    def asset_create(payload: AssetCreateRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = create_asset_candidate(root, asset_type=payload.asset_type, brief=payload.brief, target_id=payload.target_id, source=Path(payload.source) if payload.source else None, provider=payload.provider)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "asset_type": result.asset_type, "candidate_id": result.candidate_id, "candidate": rel_str(result.candidate_path, root), "report": rel_str(result.report_path, root), "run_dir": rel_str(result.run_dir, root), "validation": rel_str(result.validation_path, root), "status": result.status}

    @router.post("/asset/create-character")
    def asset_create_character(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "character"
        return asset_create(payload, http_request)

    @router.post("/asset/create-world")
    def asset_create_world(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "world"
        return asset_create(payload, http_request)

    @router.post("/asset/create-outline")
    def asset_create_outline(payload: AssetCreateRequest, http_request: Request):
        payload.asset_type = "outline"
        return asset_create(payload, http_request)

    @router.get("/asset/candidates")
    def asset_candidates(project_root: str, http_request: Request, asset_type: str = ""):
        require_api_token(http_request, api_token)
        root = safe_project_root(project_root, allowed_roots)
        try:
            items = list_asset_candidates(root, asset_type=asset_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"items": items, "count": len(items)}

    @router.post("/asset/review")
    def asset_review(payload: AssetReviewRequest, http_request: Request):
        require_api_token(http_request, api_token)
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = review_candidate_asset(root, payload.candidate, provider=payload.provider)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "candidate": rel_str(result.candidate_path, root), "report": rel_str(result.report_path, root), "json": rel_str(result.json_path, root), "agent_run": rel_str(result.agent_run_dir, root), "status": result.status, "errors": result.error_count, "warnings": result.warning_count}

    @router.post("/asset/promote")
    def asset_promote(payload: AssetPromoteRequest, http_request: Request):
        require_api_token(http_request, api_token)
        reject_bypass(payload, "POST /asset/promote")
        root = safe_project_root(payload.project_root, allowed_roots)
        try:
            result = promote_candidate_asset(root, payload.candidate, group=payload.group, approval_run_id=payload.approval_run_id, allow_unapproved=payload.allow_unapproved)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "candidate": rel_str(result.candidate_path, root), "manifest": rel_str(result.manifest_path, root), "report": rel_str(result.report_path, root), "outputs": [rel_str(path, root) for path in result.output_paths], "status": result.status}

    return router
