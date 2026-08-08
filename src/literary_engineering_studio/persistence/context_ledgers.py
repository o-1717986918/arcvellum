"""Metadata-only durable index for Agent-visible Context Ledgers."""

from __future__ import annotations

from typing import Any

from ..observability.context_ledger import CONTEXT_LEDGER_SCHEMA, parse_context_ledger
from .primitives import _now
from .sqlite_uow import SqliteUnitOfWork


CONTEXT_LEDGER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS context_ledgers (
    ledger_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    project_root_hash TEXT NOT NULL,
    session_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    plan_id TEXT NOT NULL DEFAULT '',
    plan_revision INTEGER NOT NULL DEFAULT 0,
    node_id TEXT NOT NULL DEFAULT '',
    assembled_sha256 TEXT NOT NULL,
    execution_context_digest TEXT NOT NULL DEFAULT '',
    digest TEXT NOT NULL,
    entry_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS context_ledgers_project_idx
    ON context_ledgers(project_root, created_at);
CREATE INDEX IF NOT EXISTS context_ledgers_session_idx
    ON context_ledgers(session_id, created_at);
CREATE INDEX IF NOT EXISTS context_ledgers_operation_idx
    ON context_ledgers(operation_id, created_at);
CREATE TABLE IF NOT EXISTS context_ledger_entries (
    ledger_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    source_ref TEXT NOT NULL,
    title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    partition_name TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    character_count INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    included INTEGER NOT NULL,
    truncated INTEGER NOT NULL,
    source_limit INTEGER,
    unit TEXT NOT NULL,
    preview TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    visibility_tier TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(ledger_id, position),
    UNIQUE(ledger_id, source_ref),
    FOREIGN KEY(ledger_id) REFERENCES context_ledgers(ledger_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS context_ledger_entries_source_idx
    ON context_ledger_entries(source_ref, ledger_id);
"""


class ContextLedgerRepository:
    """Persist bounded ledger metadata without copying source text into SQLite."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def record_context_ledger(
        self,
        project_root: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ledger = parse_context_ledger(payload)
        project = str(project_root or "").strip()
        if not project:
            raise ValueError("context ledger project_root is required")
        with self._uow.write(immediate=True) as connection:
            existing = connection.execute(
                "SELECT digest, project_root FROM context_ledgers WHERE ledger_id = ?",
                (ledger.ledger_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["project_root"]) != project:
                    raise ValueError("context ledger belongs to a different project")
                if str(existing["digest"]) != ledger.digest:
                    raise ValueError("context ledger conflicts with an existing digest")
                return self._read_context_ledger_tx(connection, ledger.ledger_id)
            created_at = _now()
            connection.execute(
                """
                INSERT INTO context_ledgers (
                    ledger_id, project_root, project_root_hash, session_id,
                    operation_id, plan_id, assembled_sha256,
                    plan_revision, node_id,
                    execution_context_digest, digest,
                    entry_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ledger.ledger_id,
                    project,
                    ledger.project_root_hash,
                    ledger.session_id,
                    ledger.operation_id,
                    ledger.plan_id,
                    ledger.assembled_sha256,
                    ledger.plan_revision,
                    ledger.node_id,
                    ledger.execution_context_digest,
                    ledger.digest,
                    len(ledger.entries),
                    created_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO context_ledger_entries (
                    ledger_id, position, source_ref, title, purpose,
                    partition_name, byte_count, character_count, sha256,
                    included, truncated, source_limit, unit, preview, note,
                    visibility_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        ledger.ledger_id,
                        position,
                        entry.source_ref,
                        entry.title,
                        entry.purpose,
                        entry.partition,
                        entry.byte_count,
                        entry.character_count,
                        entry.sha256,
                        int(entry.included),
                        int(entry.truncated),
                        entry.limit,
                        entry.unit,
                        entry.preview,
                        entry.note,
                        entry.visibility_tier,
                    )
                    for position, entry in enumerate(ledger.entries)
                ],
            )
            return self._read_context_ledger_tx(connection, ledger.ledger_id)

    def read_context_ledger(self, ledger_id: str) -> dict[str, Any]:
        with self._uow.read() as connection:
            return self._read_context_ledger_tx(connection, _validate_ledger_id(ledger_id))

    def list_context_ledgers(
        self,
        project_root: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._uow.read() as connection:
            rows = connection.execute(
                """
                SELECT * FROM context_ledgers
                WHERE project_root = ?
                ORDER BY created_at DESC, ledger_id DESC LIMIT ?
                """,
                (str(project_root or ""), max(1, min(1000, int(limit)))),
            ).fetchall()
        return [_ledger_metadata_row(row) for row in rows]

    @staticmethod
    def _read_context_ledger_tx(connection, ledger_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM context_ledgers WHERE ledger_id = ?",
            (_validate_ledger_id(ledger_id),),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"context ledger not found: {ledger_id}")
        entries = connection.execute(
            """
            SELECT * FROM context_ledger_entries
            WHERE ledger_id = ? ORDER BY position ASC
            """,
            (ledger_id,),
        ).fetchall()
        metadata = _ledger_metadata_row(row)
        return {
            "schema": CONTEXT_LEDGER_SCHEMA,
            "ledger_id": metadata["ledger_id"],
            "project_root": metadata["project_root"],
            "project_root_hash": metadata["project_root_hash"],
            "session_id": metadata["session_id"],
            "operation_id": metadata["operation_id"],
            "plan_id": metadata["plan_id"],
            "plan_revision": metadata["plan_revision"],
            "node_id": metadata["node_id"],
            "entries": [_entry_row(item) for item in entries],
            "assembled_sha256": metadata["assembled_sha256"],
            "execution_context_digest": metadata["execution_context_digest"],
            "digest": metadata["digest"],
            "created_at": metadata["created_at"],
        }


# Kept as an import alias for third-party code during the repository migration.
ContextLedgerStoreMixin = ContextLedgerRepository


def _validate_ledger_id(value: str) -> str:
    ledger_id = str(value or "").strip()
    if (
        not ledger_id.startswith("context-")
        or len(ledger_id) > 96
        or any(char.isspace() or ord(char) < 32 for char in ledger_id)
    ):
        raise ValueError(f"invalid context ledger id: {value}")
    return ledger_id


def _ledger_metadata_row(row) -> dict[str, Any]:
    payload = dict(row)
    payload["entry_count"] = int(payload.get("entry_count") or 0)
    payload["plan_revision"] = int(payload.get("plan_revision") or 0)
    return payload


def _entry_row(row) -> dict[str, Any]:
    payload = dict(row)
    return {
        "source_ref": payload["source_ref"],
        "title": payload["title"],
        "purpose": payload["purpose"],
        "partition": payload["partition_name"],
        "byte_count": int(payload["byte_count"]),
        "character_count": int(payload["character_count"]),
        "sha256": payload["sha256"],
        "included": bool(payload["included"]),
        "truncated": bool(payload["truncated"]),
        "limit": payload["source_limit"],
        "unit": payload["unit"],
        "preview": payload["preview"],
        "note": payload["note"],
        "visibility_tier": payload["visibility_tier"],
    }
