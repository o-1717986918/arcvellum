"""Archive structured-editor HTTP routes and stable error mapping."""

from __future__ import annotations

from typing import Callable, Protocol

from fastapi import APIRouter, HTTPException

from ...application.assets.document_codec import AssetDocumentError
from ...application.assets.structured_editor import (
    StructuredAssetService,
    StructuredDraftStaleError,
    StructuredFieldError,
)
from ..common import call_handler, project_root as resolve_project_root
from ..models import ArchiveStructuredContentRequest, ArchiveStructuredRenderRequest


class ArchiveEditorDependencies(Protocol):
    structured_editor: StructuredAssetService


def register_archive_editor_routes(
    router: APIRouter,
    deps: ArchiveEditorDependencies,
) -> None:
    @router.post("/archive/assets/{asset_id}/structure")
    def archive_structure(asset_id: str, payload: ArchiveStructuredContentRequest):
        return _structured_call(
            lambda: {
                "ok": True,
                **deps.structured_editor.project(
                    resolve_project_root(payload.project_root),
                    asset_id,
                    payload.content,
                ),
            }
        )

    @router.post("/archive/assets/{asset_id}/render-structured")
    def archive_render_structured(
        asset_id: str,
        payload: ArchiveStructuredRenderRequest,
    ):
        return _structured_call(
            lambda: {
                "ok": True,
                **deps.structured_editor.render(
                    resolve_project_root(payload.project_root),
                    asset_id,
                    payload.content,
                    payload.source_revision,
                    payload.fields,
                ),
            }
        )


def _structured_call(function: Callable[[], dict[str, object]]) -> dict[str, object]:
    try:
        return function()
    except StructuredDraftStaleError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "structured_draft_stale", "message": str(exc)},
        ) from exc
    except AssetDocumentError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "structured_document_invalid", "message": str(exc)},
        ) from exc
    except StructuredFieldError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "structured_field_invalid", "message": str(exc)},
        ) from exc
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return call_handler(lambda: _raise(exc))


def _raise(exc: Exception):
    raise exc
