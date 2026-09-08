"""SQLite persistence for lean scene transactions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

from ..application.scene_transaction import (
    SceneTransaction,
    scene_transaction_from_dict,
)
from .sqlite_uow import SqliteUnitOfWork


SCENE_TRANSACTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scene_transactions (
    transaction_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    scene_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scene_transactions_project_scene_idx
    ON scene_transactions(project_root, scene_id, updated_at);
"""


class SceneTransactionRepository:
    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def insert(self, transaction: SceneTransaction) -> SceneTransaction:
        now = _now()
        stored = replace(transaction, version=0)
        with self._uow.write() as connection:
            connection.execute(
                """
                INSERT INTO scene_transactions (
                    transaction_id, project_root, scene_id, mode, status,
                    payload_json, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    stored.transaction_id,
                    stored.project_root,
                    stored.scene_id,
                    stored.mode.value,
                    stored.status.value,
                    _payload(stored),
                    now,
                    now,
                ),
            )
        return stored

    def load(self, transaction_id: str) -> SceneTransaction:
        with self._uow.read() as connection:
            row = connection.execute(
                "SELECT payload_json, version FROM scene_transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Scene transaction not found: {transaction_id}")
        payload = json.loads(str(row["payload_json"]))
        payload["version"] = int(row["version"])
        return scene_transaction_from_dict(payload)

    def save(
        self,
        transaction: SceneTransaction,
        *,
        expected_version: int,
    ) -> SceneTransaction:
        stored = replace(transaction, version=expected_version + 1)
        with self._uow.write(immediate=True) as connection:
            cursor = connection.execute(
                """
                UPDATE scene_transactions
                SET status = ?, mode = ?, payload_json = ?, version = ?, updated_at = ?
                WHERE transaction_id = ? AND version = ?
                """,
                (
                    stored.status.value,
                    stored.mode.value,
                    _payload(stored),
                    stored.version,
                    _now(),
                    stored.transaction_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM scene_transactions WHERE transaction_id = ?",
                    (stored.transaction_id,),
                ).fetchone()
                if exists is None:
                    raise FileNotFoundError(
                        f"Scene transaction not found: {stored.transaction_id}"
                    )
                raise RuntimeError(
                    f"Scene transaction version conflict: {stored.transaction_id}"
                )
        return stored

    def latest_for_scene(
        self,
        project_root: str,
        scene_id: str,
    ) -> SceneTransaction | None:
        with self._uow.read() as connection:
            row = connection.execute(
                """
                SELECT transaction_id FROM scene_transactions
                WHERE project_root = ? AND scene_id = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_root, scene_id),
            ).fetchone()
        return self.load(str(row["transaction_id"])) if row is not None else None


def _payload(transaction: SceneTransaction) -> str:
    return json.dumps(transaction.to_dict(), ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["SCENE_TRANSACTION_SCHEMA_SQL", "SceneTransactionRepository"]
