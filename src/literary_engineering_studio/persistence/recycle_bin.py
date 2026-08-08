"""Rebuildable Archive recycle-bin indexes for the durable Studio store."""

from __future__ import annotations

from typing import Any

from .asset_revisions import _project_key, _validate_asset_key
from .asset_transactions import _relative_path
from .primitives import _now
from .sqlite_uow import SqliteUnitOfWork


RECYCLE_BIN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS archive_recycle_entries (
    entry_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    revision TEXT NOT NULL,
    status TEXT NOT NULL,
    original_path TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    entry_path TEXT NOT NULL,
    archive_receipt_path TEXT NOT NULL,
    restore_receipt_path TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL,
    archived_at TEXT NOT NULL,
    restored_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS archive_recycle_entries_project_status_idx
    ON archive_recycle_entries(project_root, status, archived_at);
CREATE INDEX IF NOT EXISTS archive_recycle_entries_project_asset_idx
    ON archive_recycle_entries(project_root, asset_id, archived_at);
"""


class RecycleBinRepository:
    """Persist the rebuildable index of archived and restored assets."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def record_recycle_entry(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_record(record)
        with self._uow.write(immediate=True) as connection:
            existing = connection.execute(
                "SELECT * FROM archive_recycle_entries WHERE entry_id = ?",
                (normalized["entry_id"],),
            ).fetchone()
            if existing is not None:
                current = dict(existing)
                if _entry_identity(current) != _entry_identity(normalized):
                    raise ValueError(
                        f"recycle entry id conflicts with existing record: {normalized['entry_id']}"
                    )
                connection.execute(
                    """
                    UPDATE archive_recycle_entries
                    SET status = ?, restore_receipt_path = ?, restored_at = ?
                    WHERE entry_id = ?
                    """,
                    (
                        normalized["status"],
                        normalized["restore_receipt_path"],
                        normalized["restored_at"],
                        normalized["entry_id"],
                    ),
                )
            else:
                _insert_recycle_entry(connection, normalized)
        return normalized

    def read_recycle_entry(self, project_root: str, entry_id: str) -> dict[str, Any]:
        project = _project_key(project_root)
        _validate_entry_id(entry_id)
        with self._uow.read() as connection:
            row = connection.execute(
                """
                SELECT * FROM archive_recycle_entries
                WHERE project_root = ? AND entry_id = ?
                """,
                (project, entry_id),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Recycle entry not found: {entry_id}")
        return dict(row)

    def list_recycle_entries(
        self,
        project_root: str,
        *,
        status: str = "",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        project = _project_key(project_root)
        normalized_status = _optional_status(status)
        bounded_limit = max(1, min(5000, int(limit)))
        query = "SELECT * FROM archive_recycle_entries WHERE project_root = ?"
        parameters: list[object] = [project]
        if normalized_status:
            query += " AND status = ?"
            parameters.append(normalized_status)
        query += " ORDER BY archived_at DESC, entry_id DESC LIMIT ?"
        parameters.append(bounded_limit)
        with self._uow.read() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [dict(row) for row in rows]


def _insert_recycle_entry(connection, record: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO archive_recycle_entries (
            entry_id, project_root, asset_id, asset_type, revision, status,
            original_path, snapshot_path, entry_path, archive_receipt_path,
            restore_receipt_path, reason, archived_at, restored_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(
            record[field]
            for field in (
                "entry_id",
                "project_root",
                "asset_id",
                "asset_type",
                "revision",
                "status",
                "original_path",
                "snapshot_path",
                "entry_path",
                "archive_receipt_path",
                "restore_receipt_path",
                "reason",
                "archived_at",
                "restored_at",
            )
        ),
    )


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    entry_id = str(record.get("entry_id") or "").strip()
    asset_id = str(record.get("asset_id") or "").strip()
    revision = str(record.get("revision") or "").strip()
    status = str(record.get("status") or "").strip()
    _validate_entry_id(entry_id)
    _validate_asset_key(asset_id, revision)
    _validate_status(status)
    normalized = {
        "entry_id": entry_id,
        "project_root": _project_key(str(record.get("project_root") or "")),
        "asset_id": asset_id,
        "asset_type": str(record.get("asset_type") or "").strip(),
        "revision": revision,
        "status": status,
        "original_path": _relative_path(record.get("original_path")),
        "snapshot_path": _relative_path(record.get("snapshot_path")),
        "entry_path": _relative_path(record.get("entry_path")),
        "archive_receipt_path": _relative_path(record.get("archive_receipt_path")),
        "restore_receipt_path": _optional_relative_path(record.get("restore_receipt_path")),
        "reason": str(record.get("reason") or "").strip(),
        "archived_at": str(record.get("archived_at") or _now()),
        "restored_at": str(record.get("restored_at") or "").strip(),
    }
    if not normalized["asset_type"] or not normalized["reason"]:
        raise ValueError("recycle entry type and reason are required")
    if status == "restored" and not normalized["restored_at"]:
        raise ValueError("restored recycle entries require restored_at")
    return normalized


def _optional_relative_path(value: object) -> str:
    raw = str(value or "").strip()
    return _relative_path(raw) if raw else ""


def _optional_status(status: str) -> str:
    value = str(status or "").strip()
    if value:
        _validate_status(value)
    return value


def _validate_status(status: str) -> None:
    if status not in {"active", "restored"}:
        raise ValueError(f"invalid recycle entry status: {status}")


def _validate_entry_id(entry_id: str) -> None:
    if not entry_id.startswith("recycle-") or len(entry_id) > 100:
        raise ValueError(f"invalid recycle entry id: {entry_id}")


def _entry_identity(record: dict[str, Any]) -> tuple[object, ...]:
    return (
        record.get("project_root"),
        record.get("asset_id"),
        record.get("revision"),
        record.get("original_path"),
        record.get("snapshot_path"),
        record.get("entry_path"),
    )
