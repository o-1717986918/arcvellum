"""Transactional Archive history repository."""

from __future__ import annotations

from typing import Any

from .asset_revisions import (
    list_asset_revisions_tx,
    read_asset_revision_tx,
    record_asset_revision_tx,
)
from .asset_transactions import (
    insert_asset_transaction_tx,
    list_asset_transactions_tx,
    normalize_asset_transaction,
)
from .sqlite_uow import SqliteUnitOfWork


class AssetHistoryRepository:
    """Persist one owner transaction and both revision indexes atomically."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def record_asset_transaction(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_asset_transaction(record)
        with self._uow.write(immediate=True) as connection:
            existing = insert_asset_transaction_tx(connection, normalized)
            if existing is not None:
                return existing
            self._record_revision(connection, normalized, "base_revision", "before_snapshot", "before")
            self._record_revision(connection, normalized, "new_revision", "after_snapshot", "after")
        return normalized

    @staticmethod
    def _record_revision(
        connection,
        record: dict[str, Any],
        revision_field: str,
        snapshot_field: str,
        role: str,
    ) -> None:
        record_asset_revision_tx(
            connection,
            project_root=record["project_root"],
            asset_id=record["asset_id"],
            revision=record[revision_field],
            transaction_id=record["transaction_id"],
            snapshot_path=record[snapshot_field],
            snapshot_role=role,
            created_at=record["created_at"],
        )

    def list_asset_transactions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._uow.read() as connection:
            return list_asset_transactions_tx(
                connection, project_root, asset_id, limit=limit
            )

    def read_asset_revision(
        self,
        project_root: str,
        asset_id: str,
        revision: str,
    ) -> dict[str, Any]:
        with self._uow.read() as connection:
            return read_asset_revision_tx(connection, project_root, asset_id, revision)

    def list_asset_revisions(
        self,
        project_root: str,
        asset_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._uow.read() as connection:
            return list_asset_revisions_tx(
                connection, project_root, asset_id, limit=limit
            )
