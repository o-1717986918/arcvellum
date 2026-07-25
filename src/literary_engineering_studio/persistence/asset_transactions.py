"""Archive owner-transaction indexes mixed into the durable Studio store."""

from __future__ import annotations

import json
from typing import Any

from .asset_revisions import _project_key, _validate_asset_key
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


class AssetTransactionStoreMixin:
    """Methods require the host JobStore connection and write-lock protocol."""

    def record_asset_transaction(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_record(record)
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
                    normalized["transaction_id"],
                    normalized["project_root"],
                    normalized["asset_id"],
                    normalized["asset_type"],
                    normalized["base_revision"],
                    normalized["new_revision"],
                    normalized["operation"],
                    normalized["authority"],
                    normalized["semantic_review"],
                    normalized["reason"],
                    _json(normalized["impact"]),
                    _json(normalized["stale_propagation"]),
                    normalized["receipt_path"],
                    normalized["transaction_path"],
                    normalized["before_snapshot"],
                    normalized["after_snapshot"],
                    normalized["created_at"],
                ),
            )
            self._record_asset_revision_tx(
                connection,
                project_root=normalized["project_root"],
                asset_id=normalized["asset_id"],
                revision=normalized["base_revision"],
                transaction_id=normalized["transaction_id"],
                snapshot_path=normalized["before_snapshot"],
                snapshot_role="before",
                created_at=normalized["created_at"],
            )
            self._record_asset_revision_tx(
                connection,
                project_root=normalized["project_root"],
                asset_id=normalized["asset_id"],
                revision=normalized["new_revision"],
                transaction_id=normalized["transaction_id"],
                snapshot_path=normalized["after_snapshot"],
                snapshot_role="after",
                created_at=normalized["created_at"],
            )
        return normalized

    def list_asset_transactions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        project = _project_key(project_root)
        _validate_asset_key(asset_id)
        bounded_limit = max(1, min(1000, int(limit)))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM archive_asset_transactions
                WHERE project_root = ? AND asset_id = ?
                ORDER BY created_at DESC, transaction_id DESC
                LIMIT ?
                """,
                (project, asset_id, bounded_limit),
            ).fetchall()
        return [_transaction_row(row) for row in rows]


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    transaction_id = str(record.get("transaction_id") or "").strip()
    _validate_transaction_id(transaction_id)
    asset_id = str(record.get("asset_id") or "").strip()
    base_revision = str(record.get("base_revision") or "").strip()
    new_revision = str(record.get("new_revision") or "").strip()
    _validate_asset_key(asset_id, base_revision)
    _validate_asset_key(asset_id, new_revision)
    normalized = {
        "transaction_id": transaction_id,
        "project_root": _project_key(str(record.get("project_root") or "")),
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
        "receipt_path": _relative_path(record.get("receipt_path")),
        "transaction_path": _relative_path(record.get("transaction_path")),
        "before_snapshot": _relative_path(record.get("before_snapshot")),
        "after_snapshot": _relative_path(record.get("after_snapshot")),
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


def _relative_path(value: object) -> str:
    path = str(value or "").strip().replace("\\", "/").lstrip("./")
    if not path or path.startswith("/") or ":" in path or ".." in path.split("/"):
        raise ValueError(f"invalid archive index path: {value}")
    return path


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
