"""Archive owner-transaction table operations and normalization."""

from __future__ import annotations

import json
from typing import Any

from .archive_primitives import (
    archive_project_key,
    archive_relative_path,
    validate_archive_asset_key,
)
from .primitives import _json, _now


ASSET_TRANSACTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS archive_asset_transactions (
    transaction_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    base_revision TEXT NOT NULL,
    new_revision TEXT NOT NULL,
    operation TEXT NOT NULL DEFAULT 'replace',
    authority TEXT NOT NULL,
    semantic_review TEXT NOT NULL,
    reason TEXT NOT NULL,
    impact_json TEXT NOT NULL,
    stale_json TEXT NOT NULL,
    receipt_path TEXT NOT NULL,
    transaction_path TEXT NOT NULL,
    before_snapshot TEXT NOT NULL,
    after_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS archive_asset_transactions_project_asset_idx
    ON archive_asset_transactions(project_root, asset_id, created_at);
"""


def insert_asset_transaction_tx(
    connection,
    normalized: dict[str, Any],
) -> dict[str, Any] | None:
    existing = connection.execute(
        "SELECT * FROM archive_asset_transactions WHERE transaction_id = ?",
        (normalized["transaction_id"],),
    ).fetchone()
    if existing is not None:
        current = _transaction_row(existing)
        if _transaction_identity(current) != _transaction_identity(normalized):
            raise ValueError(
                f"archive transaction id conflicts with existing record: {normalized['transaction_id']}"
            )
        return current
    connection.execute(
        """
        INSERT INTO archive_asset_transactions (
            transaction_id, project_root, asset_id, asset_type,
            base_revision, new_revision, operation, authority, semantic_review,
            reason, impact_json, stale_json, receipt_path,
            transaction_path, before_snapshot, after_snapshot, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized["transaction_id"], normalized["project_root"],
            normalized["asset_id"], normalized["asset_type"],
            normalized["base_revision"], normalized["new_revision"],
            normalized["operation"], normalized["authority"],
            normalized["semantic_review"], normalized["reason"],
            _json(normalized["impact"]), _json(normalized["stale_propagation"]),
            normalized["receipt_path"], normalized["transaction_path"],
            normalized["before_snapshot"], normalized["after_snapshot"],
            normalized["created_at"],
        ),
    )
    return None


def list_asset_transactions_tx(
    connection,
    project_root: str,
    asset_id: str,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    project = archive_project_key(project_root)
    validate_archive_asset_key(asset_id)
    rows = connection.execute(
        """
        SELECT * FROM archive_asset_transactions
        WHERE project_root = ? AND asset_id = ?
        ORDER BY created_at DESC, transaction_id DESC
        LIMIT ?
        """,
        (project, asset_id, max(1, min(1000, int(limit)))),
    ).fetchall()
    return [_transaction_row(row) for row in rows]


def normalize_asset_transaction(record: dict[str, Any]) -> dict[str, Any]:
    transaction_id = str(record.get("transaction_id") or "").strip()
    _validate_transaction_id(transaction_id)
    asset_id = str(record.get("asset_id") or "").strip()
    base_revision = str(record.get("base_revision") or "").strip()
    new_revision = str(record.get("new_revision") or "").strip()
    validate_archive_asset_key(asset_id, base_revision)
    validate_archive_asset_key(asset_id, new_revision)
    normalized = {
        "transaction_id": transaction_id,
        "project_root": archive_project_key(str(record.get("project_root") or "")),
        "asset_id": asset_id,
        "asset_type": str(record.get("asset_type") or "").strip(),
        "base_revision": base_revision,
        "new_revision": new_revision,
        "operation": str(record.get("operation") or "replace").strip(),
        "authority": str(record.get("authority") or "").strip(),
        "semantic_review": str(record.get("semantic_review") or "").strip(),
        "reason": str(record.get("reason") or "").strip(),
        "impact": _mapping(record, "impact"),
        "stale_propagation": _mapping(record, "stale_propagation"),
        "receipt_path": archive_relative_path(record.get("receipt_path")),
        "transaction_path": archive_relative_path(record.get("transaction_path")),
        "before_snapshot": archive_relative_path(record.get("before_snapshot")),
        "after_snapshot": archive_relative_path(record.get("after_snapshot")),
        "created_at": str(record.get("created_at") or _now()),
    }
    _validate_record_fields(normalized)
    return normalized


def _validate_transaction_id(transaction_id: str) -> None:
    if not transaction_id.startswith("owner-") or len(transaction_id) > 180:
        raise ValueError(f"invalid archive transaction id: {transaction_id}")


def _validate_record_fields(record: dict[str, Any]) -> None:
    if record["authority"] != "owner":
        raise ValueError("archive transaction authority must be owner")
    if record["operation"] not in {"replace", "create"}:
        raise ValueError("archive transaction operation must be replace or create")
    if not record["asset_type"] or not record["reason"]:
        raise ValueError("archive transaction type and reason are required")


def _mapping(record: dict[str, Any], field: str) -> dict[str, Any]:
    value = record.get(field)
    return value if isinstance(value, dict) else {}


def _transaction_row(row) -> dict[str, Any]:
    payload = dict(row)
    payload["impact"] = json.loads(str(payload.pop("impact_json") or "{}"))
    payload["stale_propagation"] = json.loads(str(payload.pop("stale_json") or "{}"))
    return payload


def _transaction_identity(record: dict[str, Any]) -> tuple[object, ...]:
    return (
        record.get("project_root"),
        record.get("asset_id"),
        record.get("base_revision"),
        record.get("new_revision"),
        record.get("operation"),
        record.get("receipt_path"),
    )
