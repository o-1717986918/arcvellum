"""Narrative Archive read, validation, impact, and owner-commit routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ...application.assets.contracts import OwnerAssetCreation, OwnerOverrideTransaction, SemanticReview
from ...application.assets.creation import (
    AssetCreationConflictError,
    AssetCreationPreviewStaleError,
    OwnerCreationService,
)
from ...application.assets.impact import build_asset_impact
from ...application.assets.loader import AssetLoader
from ...application.assets.owner_transactions import AssetVersionConflictError, OwnerTransactionService
from ...application.assets.promotion import (
    CandidateIdentityConflictError,
    CandidateNotFoundError,
    CandidatePromotionNotReadyError,
    CandidatePromotionPreviewStaleError,
    CandidatePromotionService,
)
from ...application.assets.recycle_bin import (
    ArchiveReferenceConflictError,
    RecycleBinService,
    RestoreConflictError,
)
from ...application.assets.registry import AssetViewRegistry
from ...application.assets.revisions import AssetRevisionIndex, AssetRevisionService
from ...application.assets.validation import validate_asset_content
from ...projections.archive.service import ArchiveProjectionService
from ...projections.archive.candidates import project_candidate_detail, project_candidate_list
from ..common import call_handler, project_root as resolve_project_root
from ..models import (
    ArchiveAssetCommitRequest,
    ArchiveAssetContentRequest,
    ArchiveAssetCreateCommitRequest,
    ArchiveAssetCreatePreviewRequest,
    ArchiveAssetArchiveRequest,
    ArchiveAssetRestoreRequest,
    ArchiveCandidatePromotionRequest,
    ArchiveRestorePreviewRequest,
)


@dataclass(frozen=True)
class ArchiveRouterDependencies:
    registry: AssetViewRegistry
    loader: AssetLoader
    projections: ArchiveProjectionService
    transactions: OwnerTransactionService
    creation: OwnerCreationService
    revisions: AssetRevisionService
    recycle_bin: RecycleBinService
    candidates: CandidatePromotionService
    launch_worker: Callable[[dict[str, str]], dict[str, Any]] | None = None


def default_archive_dependencies(
    index: AssetRevisionIndex,
    *,
    launch_worker: Callable[[dict[str, str]], dict[str, Any]] | None = None,
) -> ArchiveRouterDependencies:
    registry = AssetViewRegistry.default()
    loader = AssetLoader(registry)
    revisions = AssetRevisionService(index)
    recycle_bin = RecycleBinService(registry, loader, index)
    candidates = CandidatePromotionService()
    return ArchiveRouterDependencies(
        registry=registry,
        loader=loader,
        projections=ArchiveProjectionService(registry, loader, revisions, recycle_bin),
        transactions=OwnerTransactionService(registry, loader, revisions),
        creation=OwnerCreationService(registry, loader, revisions),
        revisions=revisions,
        recycle_bin=recycle_bin,
        candidates=candidates,
        launch_worker=launch_worker,
    )


def build_archive_router(deps: ArchiveRouterDependencies) -> APIRouter:
    router = APIRouter()
    _register_creation_routes(router, deps)

    @router.get("/archive/tree")
    def archive_tree(project_root: str):
        return call_handler(lambda: {"ok": True, **deps.projections.tree(resolve_project_root(project_root))})

    @router.get("/archive/candidates")
    def archive_candidates(project_root: str):
        return call_handler(
            lambda: {
                "ok": True,
                **project_candidate_list(deps.candidates.list(resolve_project_root(project_root))),
            }
        )

    @router.get("/archive/candidates/{candidate_id}")
    def archive_candidate(candidate_id: str, project_root: str):
        try:
            return {
                "ok": True,
                **project_candidate_detail(
                    deps.candidates.detail(resolve_project_root(project_root), candidate_id)
                ),
            }
        except CandidateNotFoundError as exc:
            raise _candidate_error(404, "candidate_not_found", candidate_id, exc) from exc
        except CandidateIdentityConflictError as exc:
            raise _candidate_error(409, "candidate_identity_conflict", candidate_id, exc) from exc
        except ValueError as exc:
            raise _candidate_error(400, "candidate_validation", candidate_id, exc) from exc

    @router.get("/archive/assets/{asset_id}")
    def archive_asset(asset_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, **deps.projections.detail(resolve_project_root(project_root), asset_id)})

    @router.get("/archive/assets/{asset_id}/history")
    def archive_history(asset_id: str, project_root: str):
        return call_handler(
            lambda: {"ok": True, **deps.projections.history(resolve_project_root(project_root), asset_id)}
        )

    @router.get("/archive/recycle-bin")
    def archive_recycle_bin(project_root: str):
        return call_handler(
            lambda: {"ok": True, **deps.projections.recycle_bin(resolve_project_root(project_root))}
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

    @router.post("/archive/assets/{asset_id}/archive")
    def archive_asset_to_recycle_bin(asset_id: str, payload: ArchiveAssetArchiveRequest):
        return _archive_asset(deps, asset_id, payload)

    @router.post("/archive/assets/{asset_id}/restore")
    def restore_asset_from_recycle_bin(asset_id: str, payload: ArchiveAssetRestoreRequest):
        return _restore_asset(deps, asset_id, payload)

    @router.post("/archive/candidates/{candidate_id}/promote")
    def promote_archive_candidate(candidate_id: str, payload: ArchiveCandidatePromotionRequest):
        return _promote_candidate(deps, candidate_id, payload)

    return router


def _register_creation_routes(
    router: APIRouter,
    deps: ArchiveRouterDependencies,
) -> None:
    @router.get("/archive/creation/options")
    def archive_creation_options(project_root: str):
        return call_handler(
            lambda: {"ok": True, **deps.creation.options(resolve_project_root(project_root))}
        )

    @router.post("/archive/creation/preview")
    def archive_creation_preview(payload: ArchiveAssetCreatePreviewRequest):
        return _preview_creation(deps, payload)

    @router.post("/archive/creation/commit")
    def archive_creation_commit(payload: ArchiveAssetCreateCommitRequest):
        return _commit_creation(deps, payload)


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


def _preview_creation(
    deps: ArchiveRouterDependencies,
    payload: ArchiveAssetCreatePreviewRequest,
) -> dict[str, Any]:
    creation = _creation_from_payload(deps, payload)
    try:
        preview = deps.creation.preview(resolve_project_root(payload.project_root), creation)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))
    return {"ok": True, "preview": preview}


def _commit_creation(
    deps: ArchiveRouterDependencies,
    payload: ArchiveAssetCreateCommitRequest,
) -> dict[str, Any]:
    creation = _creation_from_payload(deps, payload)
    try:
        receipt = deps.creation.create(
            resolve_project_root(payload.project_root),
            creation,
            preview_digest=payload.preview_digest,
        )
    except AssetCreationConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "asset_creation_conflict",
                "message": str(exc),
                "asset_id": creation.asset_id,
            },
        ) from exc
    except AssetCreationPreviewStaleError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "creation_preview_stale",
                "message": str(exc),
                "asset_id": creation.asset_id,
            },
        ) from exc
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))
    return {"ok": True, "asset_id": creation.asset_id, "receipt": receipt}


def _creation_from_payload(
    deps: ArchiveRouterDependencies,
    payload: ArchiveAssetCreatePreviewRequest,
) -> OwnerAssetCreation:
    try:
        semantic_review = SemanticReview(payload.semantic_review)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation", "message": "semantic_review must be required or waived"},
        ) from exc
    try:
        definition = deps.registry.definition(payload.asset_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "creation_validation", "message": str(exc)},
        ) from exc
    if not definition.supports_create:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "creation_not_supported",
                "message": f"asset creation is not supported for {payload.asset_type}",
            },
        )
    local_id = definition.fixed_id or payload.local_id.strip()
    asset_id = deps.registry.asset_id(definition, local_id)
    try:
        deps.registry.parse_asset_id(asset_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "creation_validation", "message": str(exc)},
        ) from exc
    return OwnerAssetCreation.create(
        asset_id=asset_id,
        asset_type=definition.asset_type,
        content=payload.content,
        semantic_review=semantic_review,
        reason=payload.reason,
        expected_impacts=tuple(str(item) for item in payload.expected_impacts),
    )


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


def _archive_asset(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveAssetArchiveRequest,
) -> dict[str, Any]:
    try:
        receipt = deps.recycle_bin.archive(
            resolve_project_root(payload.project_root),
            asset_id,
            base_revision=payload.base_revision,
            reason=payload.reason,
        )
    except AssetVersionConflictError as exc:
        raise _conflict("version_conflict", asset_id, exc) from exc
    except ArchiveReferenceConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "archive_reference_conflict",
                "message": str(exc),
                "asset_id": asset_id,
                "blockers": exc.blockers,
            },
        ) from exc
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))
    return {"ok": True, "receipt": receipt}


def _restore_asset(
    deps: ArchiveRouterDependencies,
    asset_id: str,
    payload: ArchiveAssetRestoreRequest,
) -> dict[str, Any]:
    try:
        receipt = deps.recycle_bin.restore(
            resolve_project_root(payload.project_root),
            asset_id,
            entry_id=payload.entry_id,
            reason=payload.reason,
        )
    except RestoreConflictError as exc:
        raise _conflict("restore_conflict", asset_id, exc) from exc
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))
    return {"ok": True, "receipt": receipt}


def _promote_candidate(
    deps: ArchiveRouterDependencies,
    candidate_id: str,
    payload: ArchiveCandidatePromotionRequest,
) -> dict[str, object]:
    try:
        request = deps.candidates.worker_request(
            resolve_project_root(payload.project_root),
            candidate_id,
            preview_digest=payload.preview_digest,
        )
        if deps.launch_worker is None:
            raise RuntimeError("Archive candidate Worker launcher is unavailable")
        job = deps.launch_worker(request)
    except CandidateNotFoundError as exc:
        raise _candidate_error(404, "candidate_not_found", candidate_id, exc) from exc
    except CandidateIdentityConflictError as exc:
        raise _candidate_error(409, "candidate_identity_conflict", candidate_id, exc) from exc
    except CandidatePromotionNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "promotion_not_ready",
                "message": str(exc),
                "candidate_id": candidate_id,
                "blockers": list(exc.blockers),
            },
        ) from exc
    except CandidatePromotionPreviewStaleError as exc:
        raise _candidate_error(409, "promotion_preview_stale", candidate_id, exc) from exc
    except ValueError as exc:
        raise _candidate_error(400, "candidate_validation", candidate_id, exc) from exc
    except RuntimeError as exc:
        raise _candidate_error(503, "worker_unavailable", candidate_id, exc) from exc
    return {
        "ok": True,
        "candidate_id": candidate_id,
        "job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or "queued"),
    }


def _conflict(code: str, asset_id: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": str(exc), "asset_id": asset_id},
    )


def _candidate_error(status_code: int, code: str, candidate_id: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc), "candidate_id": candidate_id},
    )


def _raise(exc: Exception):
    raise exc
