"""Archive asset revision indexes mixed into the durable Studio store."""

from __future__ import annotations

from typing import Any

from .primitives import _now


ASSET_REVISION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS archive_asset_revisions (
    project_root TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    snapshot_role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(project_root, asset_id, revision)
);
CREATE INDEX IF NOT EXISTS archive_asset_revisions_transaction_idx
    ON archive_asset_revisions(transaction_id);
"""


class AssetRevisionStoreMixin:
    """Methods require the host JobStore connection and write-lock protocol."""

    def read_asset_revision(
        self,
        project_root: str,
        asset_id: str,
        revision: str,
    ) -> dict[str, Any]:
        project = _project_key(project_root)
        _validate_asset_key(asset_id, revision)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT project_root, asset_id, revision, transaction_id,
                       snapshot_path, snapshot_role, created_at
                FROM archive_asset_revisions
                WHERE project_root = ? AND asset_id = ? AND revision = ?
                """,
                (project, asset_id, revision),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Archive revision not found: {asset_id}@{revision}")
        return dict(row)

    def list_asset_revisions(
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
                SELECT project_root, asset_id, revision, transaction_id,
                       snapshot_path, snapshot_role, created_at
                FROM archive_asset_revisions
                WHERE project_root = ? AND asset_id = ?
                ORDER BY created_at DESC, revision DESC
                LIMIT ?
                """,
                (project, asset_id, bounded_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _record_asset_revision_tx(
        connection,
        *,
        project_root: str,
        asset_id: str,
        revision: str,
        transaction_id: str,
        snapshot_path: str,
        snapshot_role: str,
        created_at: str,
    ) -> None:
        _validate_asset_key(asset_id, revision)
        connection.execute(
            """
            INSERT OR IGNORE INTO archive_asset_revisions (
                project_root, asset_id, revision, transaction_id,
                snapshot_path, snapshot_role, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _project_key(project_root),
                asset_id,
                revision,
                transaction_id,
                snapshot_path,
                snapshot_role,
                created_at or _now(),
            ),
        )


def _project_key(project_root: str) -> str:
    value = str(project_root or "").strip().replace("\\", "/").rstrip("/")
    if not value:
        raise ValueError("archive project root must not be empty")
    return value.casefold()


def _validate_asset_key(asset_id: str, revision: str = "") -> None:
    if not asset_id or ":" not in asset_id or len(asset_id) > 260:
        raise ValueError(f"invalid archive asset id: {asset_id}")
    if revision and (not revision.startswith("sha256:") or len(revision) != 71):
        raise ValueError(f"invalid archive revision: {revision}")
