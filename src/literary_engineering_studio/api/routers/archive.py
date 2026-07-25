"""Narrative Archive read, validation, impact, and owner-commit routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException

from ...application.assets.contracts import OwnerOverrideTransaction, SemanticReview
from ...application.assets.impact import build_asset_impact
from ...application.assets.loader import AssetLoader
from ...application.assets.owner_transactions import AssetVersionConflictError, OwnerTransactionService
from ...application.assets.registry import AssetViewRegistry
from ...application.assets.revisions import AssetRevisionIndex, AssetRevisionService
from ...application.assets.validation import validate_asset_content
from ...projections.archive.service import ArchiveProjectionService
from ..common import call_handler, project_root as resolve_project_root
from ..models import (
    ArchiveAssetCommitRequest,
    ArchiveAssetContentRequest,
    ArchiveRestorePreviewRequest,
)


@dataclass(frozen=True)
class ArchiveRouterDependencies:
    registry: AssetViewRegistry
    loader: AssetLoader
    projections: ArchiveProjectionService
    transactions: OwnerTransactionService
    revisions: AssetRevisionService


def default_archive_dependencies(index: AssetRevisionIndex) -> ArchiveRouterDependencies:
    registry = AssetViewRegistry.default()
    loader = AssetLoader(registry)
    revisions = AssetRevisionService(index)
    return ArchiveRouterDependencies(
        registry=registry,
        loader=loader,
        projections=ArchiveProjectionService(registry, loader, revisions),
        transactions=OwnerTransactionService(registry, loader, revisions),
        revisions=revisions,
    )


def build_archive_router(deps: ArchiveRouterDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/archive/tree")
    def archive_tree(project_root: str):
        return call_handler(lambda: {"ok": True, **deps.projections.tree(resolve_project_root(project_root))})

    @router.get("/archive/assets/{asset_id}")
    def archive_asset(asset_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, **deps.projections.detail(resolve_project_root(project_root), asset_id)})

    @router.get("/archive/assets/{asset_id}/history")
    def archive_history(asset_id: str, project_root: str):
        return call_handler(
            lambda: {"ok": True, **deps.projections.history(resolve_project_root(project_root), asset_id)}
        )

    @router.post("/archive/assets/{asset_id}/validate")
    def archive_validate(asset_id: str, payload: ArchiveAssetContentRequest):
        return call_handler(lambda: _validate_asset(deps, asset_id, payload))

    @router.post("/archive/assets/{asset_id}/impact")
    def archive_impact(asset_id: str, payload: ArchiveAssetContentRequest):
        return call_handler(lambda: _impact_asset(deps, asset_id, payload))

    @router.post("/archive/assets/{asset_id}/commit")
    def archive_commit(asset_id: str, payload: ArchiveAssetCommitRequest):
        return _commit_asset(deps, asset_id, payload)

    @router.post("/archive/assets/{asset_id}/restore/preview")
    def archive_restore_preview(asset_id: str, payload: ArchiveRestorePreviewRequest):
        return call_handler(lambda: _restore_preview(deps, asset_id, payload))

    return router


def _validate_asset(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveAssetContentRequest,
) -> dict[str, Any]:
    root = resolve_project_root(payload.project_root)
    definition, local_id = deps.registry.parse_asset_id(asset_id)
    deps.loader.load(root, asset_id)
    result = validate_asset_content(root, definition, local_id, payload.content)
    return {"ok": True, "schema": "arcvellum/archive-validation/v1", "validation": result.as_dict()}


def _impact_asset(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveAssetContentRequest,
) -> dict[str, Any]:
    root = resolve_project_root(payload.project_root)
    asset = deps.loader.load(root, asset_id)
    return {"ok": True, "impact": build_asset_impact(root, asset, payload.content)}


def _commit_asset(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveAssetCommitRequest,
) -> dict[str, Any]:
    try:
        semantic_review = SemanticReview(payload.semantic_review)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation", "message": "semantic_review must be required or waived"},
        ) from exc
    definition, _ = deps.registry.parse_asset_id(asset_id)
    transaction = OwnerOverrideTransaction.create(
        asset_id=asset_id,
        asset_type=definition.asset_type,
        base_revision=payload.base_revision,
        content=payload.content,
        semantic_review=semantic_review,
        reason=payload.reason,
        expected_impacts=tuple(str(item) for item in payload.expected_impacts),
    )
    try:
        receipt = deps.transactions.commit(resolve_project_root(payload.project_root), transaction)
    except AssetVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "message": str(exc), "asset_id": asset_id},
        ) from exc
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))
    return {"ok": True, "receipt": receipt}


def _restore_preview(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveRestorePreviewRequest,
) -> dict[str, Any]:
    root = resolve_project_root(payload.project_root)
    asset = deps.loader.load(root, asset_id)
    content, revision = deps.revisions.snapshot_content(root, asset_id, payload.revision)
    transaction = OwnerOverrideTransaction.create(
        asset_id=asset_id,
        asset_type=asset.asset_type,
        base_revision=asset.revision,
        content=content,
        semantic_review=SemanticReview.WAIVED,
        reason=payload.reason,
    )
    return {
        "ok": True,
        "restore": {
            "asset_id": asset_id,
            "revision": payload.revision,
            "current_revision": asset.revision,
            "transaction_id": revision["transaction_id"],
            "preview_only": True,
        },
        "preview": deps.transactions.preview(root, transaction),
    }


def _raise(exc: Exception):
    raise exc
