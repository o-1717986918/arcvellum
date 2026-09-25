"""Project Agent adapters for the same owner archive services used by the UI."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..application.assets.contracts import OwnerAssetCreation, OwnerOverrideTransaction, SemanticReview
from .action_receipts import action_receipt


def archive_read_action(archive: Any):
    def read(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        section = str(arguments.get("section") or "tree").strip()
        asset_id = str(arguments.get("asset_id") or "").strip()
        offset = max(0, int(arguments.get("offset") or 0))
        if section == "tree":
            tree = archive.projections.tree(root)
            items = tree["items"]
            return {
                "schema": tree["schema"], "count": tree["count"], "offset": offset,
                "items": items[offset:offset + 50], "has_more": offset + 50 < len(items),
                "groups": [{key: value for key, value in group.items() if key != "items"}
                           for group in tree["groups"]],
            }
        if section == "creation_options":
            return archive.creation.options(root)
        if section == "recycle_bin":
            payload = archive.projections.recycle_bin(root)
            items = payload["items"]
            return {**payload, "items": items[offset:offset + 30], "offset": offset,
                    "has_more": offset + 30 < len(items)}
        if not asset_id:
            raise ValueError("project_archive_read requires asset_id for detail or history")
        if section == "history":
            payload = archive.projections.history(root, asset_id)
            transactions, revisions = payload["transactions"], payload["revisions"]
            return {**payload, "transactions": transactions[offset:offset + 20],
                    "revisions": revisions[offset:offset + 20], "offset": offset,
                    "has_more": offset + 20 < max(len(transactions), len(revisions))}
        if section != "detail":
            raise ValueError("unsupported project_archive_read section")
        detail = archive.projections.detail(root, asset_id)
        asset = dict(detail["asset"])
        content = str(asset.pop("content"))
        if offset > len(content):
            raise ValueError("archive content offset exceeds length")
        return {
            "schema": detail["schema"], "asset": asset,
            "content": content[offset:offset + 12000], "offset": offset,
            "content_length": len(content), "has_more": offset + 12000 < len(content),
        }

    return read


def archive_change_action(archive: Any, invalidate_project: Any | None = None):
    def change(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments.get("operation") or "").strip().lower()
        asset_id = str(arguments.get("asset_id") or "").strip()
        reason = str(arguments.get("reason") or "").strip()
        if len(reason) < 6:
            raise ValueError("project_archive_change requires an explanatory reason")
        if operation == "create":
            asset_id, receipt = _create_asset(archive, root, arguments, reason)
        elif operation == "replace":
            definition, _ = archive.registry.parse_asset_id(asset_id)
            transaction = OwnerOverrideTransaction.create(
                asset_id=asset_id, asset_type=definition.asset_type,
                base_revision=str(arguments.get("base_revision") or ""),
                content=_content(arguments), semantic_review=SemanticReview.WAIVED, reason=reason,
            )
            receipt = archive.transactions.commit(root, transaction)
        elif operation == "archive":
            receipt = archive.recycle_bin.archive(
                root, asset_id, base_revision=str(arguments.get("base_revision") or ""), reason=reason,
            )
        elif operation == "restore":
            receipt = archive.recycle_bin.restore(
                root, asset_id, entry_id=str(arguments.get("entry_id") or ""), reason=reason,
            )
        else:
            raise ValueError("project_archive_change operation must be create, replace, archive, or restore")
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-archive")
        return {
            "ok": True, "operation": operation, "asset_id": asset_id,
            "receipt": receipt, "action_receipt": action_receipt(f"archive_{operation}", receipt),
        }

    return change


def _create_asset(archive: Any, root: Path, arguments: Mapping[str, Any], reason: str) -> tuple[str, Any]:
    definition = archive.registry.definition(str(arguments.get("asset_type") or ""))
    local_id = definition.fixed_id or str(arguments.get("local_id") or "").strip()
    asset_id = archive.registry.asset_id(definition, local_id)
    creation = OwnerAssetCreation.create(
        asset_id=asset_id, asset_type=definition.asset_type,
        content=_content(arguments), semantic_review=SemanticReview.WAIVED, reason=reason,
    )
    preview = archive.creation.preview(root, creation)
    receipt = archive.creation.create(root, creation, preview_digest=str(preview["preview_digest"]))
    return asset_id, receipt


def _content(arguments: Mapping[str, Any]) -> str:
    value = arguments.get("content")
    if not isinstance(value, str):
        raise ValueError("archive content must be text")
    return value


__all__ = ["archive_change_action", "archive_read_action"]
