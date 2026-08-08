"""Durable job, event, lock, and run-resource storage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
import uuid
from typing import Any

from .asset_history import AssetHistoryRepository
from .autopilot_runs import AutopilotRepository
from .creative_plans import CreativePlanRepository
from .context_ledgers import ContextLedgerRepository
from .facade import RepositoryMethod
from .mutation_receipts import MutationReceiptRepository
from .recycle_bin import RecycleBinRepository
from .schema import initialize_schema
from .sessions import SessionRepository
from .sqlite_uow import SqliteUnitOfWork
from .primitives import (
    ACTIVE_STATUSES,
    DATABASE_SCHEMA_VERSION,
    EVENT_RETENTION_PER_JOB,
    EVENT_SCHEMA,
    JOB_SCHEMA,
    TERMINAL_STATUSES,
    _json,
    _now,
    _public_request,
    _redact,
    _validate_advisor_id,
    _validate_agent_session_id,
    _validate_job_id,
)


class JobStore:
    def __init__(self, location: Path):
        resolved = location.expanduser().resolve()
        self.path = resolved if resolved.suffix in {".db", ".sqlite", ".sqlite3"} else resolved / "studio.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._uow = SqliteUnitOfWork(self.path)
        self._write_lock = self._uow.write_lock
        self.autopilot_runs = AutopilotRepository(self._uow)
        self.sessions = SessionRepository(self._uow)
        self.context_ledgers = ContextLedgerRepository(self._uow)
        self.mutation_receipts = MutationReceiptRepository(self._uow)
        self.creative_plans = CreativePlanRepository(self._uow)
        self.recycle_bin = RecycleBinRepository(self._uow)
        self.asset_history = AssetHistoryRepository(self._uow)
        self.migration_backup = self._backup_before_migration()
        self._initialize()

    def create(self, request: dict[str, Any], *, idempotency_key: str = "") -> dict[str, Any]:
        normalized_key = str(idempotency_key or "").strip()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if normalized_key:
                existing = connection.execute(
                    "SELECT * FROM jobs WHERE idempotency_key = ?",
                    (normalized_key,),
                ).fetchone()
                if existing is not None:
                    return self._job_row(existing)
            job_id = f"job-{uuid.uuid4().hex[:16]}"
            now = _now()
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, status, created_at, updated_at, request_json, result_json,
                    error, idempotency_key, revision
                ) VALUES (?, 'queued', ?, ?, ?, '{}', '', ?, 0)
                """,
                (job_id, now, now, _json(request), normalized_key),
            )
            self._append_event_tx(connection, job_id, "run.queued", {"request": _public_request(request)})
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert row is not None
            return self._job_row(row)

    # Compatibility API stays explicit while calls bind to real repositories.
    create_autopilot_run = RepositoryMethod("autopilot_runs")
    read_autopilot_run = RepositoryMethod("autopilot_runs")
    latest_autopilot_run = RepositoryMethod("autopilot_runs")
    update_autopilot_run = RepositoryMethod("autopilot_runs")
    update_autopilot_run_policy = RepositoryMethod("autopilot_runs")
    advance_autopilot_run = RepositoryMethod("autopilot_runs")
    acquire_autopilot_lease = RepositoryMethod("autopilot_runs")
    renew_autopilot_lease = RepositoryMethod("autopilot_runs")
    release_autopilot_lease = RepositoryMethod("autopilot_runs")
    append_autopilot_event = RepositoryMethod("autopilot_runs")
    autopilot_events_since = RepositoryMethod("autopilot_runs")
    record_delegated_decision = RepositoryMethod("autopilot_runs")
    delegated_decisions = RepositoryMethod("autopilot_runs")
    recover_autopilot_runs = RepositoryMethod("autopilot_runs")

    create_advisor_session = RepositoryMethod("sessions")
    read_advisor_session = RepositoryMethod("sessions")
    list_advisor_sessions = RepositoryMethod("sessions")
    upsert_agent_session = RepositoryMethod("sessions")
    read_agent_session = RepositoryMethod("sessions")
    list_agent_sessions = RepositoryMethod("sessions")
    append_advisor_message = RepositoryMethod("sessions")
    save_advisor_memory = RepositoryMethod("sessions")
    save_delegation_policy = RepositoryMethod("sessions")
    read_delegation_policy = RepositoryMethod("sessions")
    upsert_advisor_inbox = RepositoryMethod("sessions")
    advisor_inbox = RepositoryMethod("sessions")
    mark_advisor_inbox_read = RepositoryMethod("sessions")
    reader_state = RepositoryMethod("sessions")
    save_reader_position = RepositoryMethod("sessions")
    set_reader_bookmark = RepositoryMethod("sessions")

    record_context_ledger = RepositoryMethod("context_ledgers")
    read_context_ledger = RepositoryMethod("context_ledgers")
    list_context_ledgers = RepositoryMethod("context_ledgers")

    record_mutation_receipt = RepositoryMethod("mutation_receipts")
    read_mutation_receipt = RepositoryMethod("mutation_receipts")
    list_mutation_receipts = RepositoryMethod("mutation_receipts")

    reserve_creative_plan_revision = RepositoryMethod("creative_plans")
    finalize_creative_plan_revision = RepositoryMethod("creative_plans")
    read_creative_plan = RepositoryMethod("creative_plans")
    list_creative_plans = RepositoryMethod("creative_plans")
    read_creative_plan_revision = RepositoryMethod("creative_plans")
    authorize_creative_plan_revision = RepositoryMethod("creative_plans")
    activate_creative_plan = RepositoryMethod("creative_plans")
    creative_plan_events = RepositoryMethod("creative_plans")

    record_recycle_entry = RepositoryMethod("recycle_bin")
    read_recycle_entry = RepositoryMethod("recycle_bin")
    list_recycle_entries = RepositoryMethod("recycle_bin")

    record_asset_transaction = RepositoryMethod("asset_history")
    list_asset_transactions = RepositoryMethod("asset_history")
    read_asset_revision = RepositoryMethod("asset_history")
    list_asset_revisions = RepositoryMethod("asset_history")

    def read(self, job_id: str) -> dict[str, Any]:
        _validate_job_id(job_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Worker job not found: {job_id}")
        return self._job_row(row)

    def update(self, job_id: str, **updates: object) -> dict[str, Any]:
        _validate_job_id(job_id)
        allowed = {
            "status",
            "started_at",
            "finished_at",
            "result",
            "error",
            "lease_owner",
            "lease_expires_at",
            "heartbeat_at",
        }
        unknown = sorted(set(updates) - allowed)
        if unknown:
            raise ValueError("unsupported job fields: " + ", ".join(unknown))
        assignments: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            column = "result_json" if key == "result" else key
            assignments.append(f"{column} = ?")
            values.append(_json(value) if key == "result" else value)
        assignments.extend(["updated_at = ?", "revision = revision + 1"])
        values.append(_now())
        values.append(job_id)
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if current is None:
                raise FileNotFoundError(f"Worker job not found: {job_id}")
            connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id = ?",
                tuple(values),
            )
            new_status = str(updates.get("status") or "")
            if new_status and new_status != str(current["status"]):
                self._append_event_tx(connection, job_id, f"run.{new_status}", {"status": new_status})
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert row is not None
            return self._job_row(row)

    def claim(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> bool:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=max(10, lease_seconds))).isoformat()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"Worker job not found: {job_id}")
            if row["status"] not in {"queued", "interrupted"}:
                return False
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running', started_at = COALESCE(started_at, ?), updated_at = ?,
                    lease_owner = ?, lease_expires_at = ?, heartbeat_at = ?, revision = revision + 1
                WHERE job_id = ?
                """,
                (now.isoformat(), now.isoformat(), worker_id, expires, now.isoformat(), job_id),
            )
            self._append_event_tx(connection, job_id, "run.started", {"worker_id": worker_id})
            return True

    def heartbeat(self, job_id: str, worker_id: str, *, lease_seconds: int = 60) -> None:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=max(10, lease_seconds))).isoformat()
        with self._write_lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                WHERE job_id = ? AND lease_owner = ? AND status IN ('running', 'stopping')
                """,
                (now.isoformat(), expires, now.isoformat(), job_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"job lease is not owned by {worker_id}: {job_id}")

    def heartbeat_execution(
        self,
        job_id: str,
        worker_id: str,
        lock_key: str,
        *,
        lease_seconds: int = 60,
    ) -> None:
        """Renew job and project-write leases in one transaction."""

        _validate_job_id(job_id)
        if not lock_key.strip():
            raise ValueError("lock key must not be empty")
        now = datetime.now(timezone.utc)
        job_expires = (now + timedelta(seconds=max(10, lease_seconds))).isoformat()
        lock_expires = (now + timedelta(seconds=max(30, lease_seconds * 2))).isoformat()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                """
                UPDATE jobs SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                WHERE job_id = ? AND lease_owner = ? AND status IN ('running', 'stopping')
                """,
                (now.isoformat(), job_expires, now.isoformat(), job_id, worker_id),
            )
            if job.rowcount != 1:
                raise RuntimeError(f"job lease is not owned by {worker_id}: {job_id}")
            lock = connection.execute(
                """
                UPDATE project_locks SET lease_expires_at = ?, updated_at = ?
                WHERE lock_key = ? AND job_id = ? AND lease_owner = ?
                """,
                (lock_expires, now.isoformat(), lock_key, job_id, worker_id),
            )
            if lock.rowcount != 1:
                raise RuntimeError(
                    f"project execution lease is not owned by {worker_id}: {lock_key}"
                )

    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        _validate_job_id(job_id)
        if not isinstance(data, dict):
            raise ValueError("run event data must be an object")
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            return self._append_event_tx(connection, job_id, event_type, data)

    def events_since(self, job_id: str, after: int = 0, *, limit: int = 200) -> list[dict[str, Any]]:
        _validate_job_id(job_id)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, job_id, event_type, at, data_json
                FROM run_events WHERE job_id = ? AND sequence > ?
                ORDER BY sequence ASC LIMIT ?
                """,
                (job_id, max(0, int(after)), max(1, min(1000, int(limit)))),
            ).fetchall()
        return [self._event_row(row) for row in rows]

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT job_id FROM jobs WHERE status IN ('running', 'stopping')"
            ).fetchall()
            for row in rows:
                job_id = str(row["job_id"])
                connection.execute(
                    """
                    UPDATE jobs SET status = 'interrupted', updated_at = ?, lease_owner = '',
                        lease_expires_at = '', heartbeat_at = '', revision = revision + 1
                    WHERE job_id = ?
                    """,
                    (now, job_id),
                )
                self._append_event_tx(connection, job_id, "run.interrupted", {"reason": "application-restart"})
                recovered.append(job_id)
        return recovered

    def acquire_lock(self, lock_key: str, job_id: str, worker_id: str, *, lease_seconds: int = 120) -> bool:
        if not lock_key.strip():
            raise ValueError("lock key must not be empty")
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=max(30, lease_seconds))).isoformat()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM project_locks WHERE lease_expires_at < ?", (now.isoformat(),))
            existing = connection.execute(
                "SELECT job_id FROM project_locks WHERE lock_key = ?",
                (lock_key,),
            ).fetchone()
            if existing is not None and existing["job_id"] != job_id:
                return False
            connection.execute(
                """
                INSERT INTO project_locks (lock_key, job_id, lease_owner, lease_expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lock_key) DO UPDATE SET
                    job_id = excluded.job_id,
                    lease_owner = excluded.lease_owner,
                    lease_expires_at = excluded.lease_expires_at,
                    updated_at = excluded.updated_at
                """,
                (lock_key, job_id, worker_id, expires, now.isoformat()),
            )
            self._append_event_tx(connection, job_id, "lock.acquired", {"lock_key": lock_key})
            return True

    def release_lock(self, lock_key: str, job_id: str) -> None:
        with self._write_lock, self._connection() as connection:
            connection.execute(
                "DELETE FROM project_locks WHERE lock_key = ? AND job_id = ?",
                (lock_key, job_id),
            )
            self._append_event_tx(connection, job_id, "lock.released", {"lock_key": lock_key})

    def register_resources(
        self,
        job_id: str,
        *,
        formal_project: str,
        task_sandbox: str,
        agent_session: str,
        run_workspace: str,
        state: str = "prepared",
    ) -> None:
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO run_resources (
                    job_id, formal_project, task_sandbox, agent_session, run_workspace, state, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    formal_project = excluded.formal_project,
                    task_sandbox = excluded.task_sandbox,
                    agent_session = excluded.agent_session,
                    run_workspace = excluded.run_workspace,
                    state = excluded.state,
                    updated_at = excluded.updated_at
                """,
                (job_id, formal_project, task_sandbox, agent_session, run_workspace, state, now),
            )

    def read_resources(self, job_id: str) -> dict[str, str] | None:
        _validate_job_id(job_id)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT formal_project, task_sandbox, agent_session, run_workspace, state, updated_at
                FROM run_resources WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def health(self) -> dict[str, Any]:
        with self._connection() as connection:
            job_count = int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            active_count = int(
                connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','stopping')").fetchone()[0]
            )
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        return {
            "ready": version == DATABASE_SCHEMA_VERSION,
            "database": str(self.path),
            "schema_version": version,
            "job_count": job_count,
            "active_job_count": active_count,
            "migration_backup": str(self.migration_backup) if self.migration_backup else "",
        }

    def _backup_before_migration(self) -> Path | None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
        if version > DATABASE_SCHEMA_VERSION:
            raise RuntimeError(
                f"Studio database schema {version} is newer than supported {DATABASE_SCHEMA_VERSION}"
            )
        if version == DATABASE_SCHEMA_VERSION:
            return None
        backup_root = self.path.parent / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_root / f"{self.path.stem}-schema-{version}-{stamp}{self.path.suffix}"
        shutil.copy2(self.path, backup)
        return backup

    def _initialize(self) -> None:
        with self._write_lock, self._connection() as connection:
            initialize_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        return self._uow.connect()

    @contextmanager
    def _connection(self):
        with self._uow.connection() as connection:
            yield connection

    def _append_event_tx(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if not event_type or any(char.isspace() for char in event_type):
            raise ValueError(f"invalid event type: {event_type}")
        at = _now()
        cursor = connection.execute(
            "INSERT INTO run_events (job_id, event_type, at, data_json) VALUES (?, ?, ?, ?)",
            (job_id, event_type, at, _json(_redact(data))),
        )
        connection.execute(
            """
            DELETE FROM run_events
            WHERE job_id = ? AND sequence NOT IN (
                SELECT sequence FROM run_events WHERE job_id = ?
                ORDER BY sequence DESC LIMIT ?
            )
            """,
            (job_id, job_id, EVENT_RETENTION_PER_JOB),
        )
        return {
            "schema": EVENT_SCHEMA,
            "sequence": int(cursor.lastrowid),
            "job_id": job_id,
            "event": event_type,
            "at": at,
            "data": _redact(data),
        }

    @staticmethod
    def _job_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": JOB_SCHEMA,
            "job_id": row["job_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "request": json.loads(row["request_json"]),
            "result": json.loads(row["result_json"]),
            "error": row["error"],
            "lease_owner": row["lease_owner"],
            "lease_expires_at": row["lease_expires_at"],
            "heartbeat_at": row["heartbeat_at"],
            "idempotency_key": row["idempotency_key"],
            "revision": int(row["revision"]),
        }

    @staticmethod
    def _event_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": EVENT_SCHEMA,
            "sequence": int(row["sequence"]),
            "job_id": row["job_id"],
            "event": row["event_type"],
            "at": row["at"],
            "data": json.loads(row["data_json"]),
        }
