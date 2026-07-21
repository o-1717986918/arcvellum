"""Durable job, event, lock, and run-resource storage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
import threading
import uuid
from typing import Any


JOB_SCHEMA = "literary-engineering-studio/worker-job/v0.3"
EVENT_SCHEMA = "literary-engineering-studio/run-event/v0.3"
EVENT_RETENTION_PER_JOB = 5000
DATABASE_SCHEMA_VERSION = 7
ACTIVE_STATUSES = {"queued", "running", "stopping"}
TERMINAL_STATUSES = {
    "complete",
    "failed",
    "cancelled",
    "runtime_failed",
    "blocked_by_core_gate",
    "blocked_empty_submission",
    "waiting_human",
    "waiting_host_agent",
    "route_ready",
}


class JobStore:
    def __init__(self, location: Path):
        resolved = location.expanduser().resolve()
        self.path = resolved if resolved.suffix in {".db", ".sqlite", ".sqlite3"} else resolved / "studio.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
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

    def create_advisor_session(self, project_root: str, snapshot_digest: str, *, title: str = "项目问答") -> dict[str, Any]:
        session_id = f"advisor-{uuid.uuid4().hex[:16]}"
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO advisor_sessions (
                    session_id, project_root, snapshot_digest, title, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_root, snapshot_digest, title.strip() or "项目问答", now, now),
            )
        return self.read_advisor_session(session_id)

    def read_advisor_session(self, session_id: str) -> dict[str, Any]:
        _validate_advisor_id(session_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM advisor_sessions WHERE session_id = ?", (session_id,)).fetchone()
            messages = connection.execute(
                """
                SELECT sequence, role, at, payload_json FROM advisor_messages
                WHERE session_id = ? ORDER BY sequence ASC
                """,
                (session_id,),
            ).fetchall()
            summary_row = connection.execute(
                "SELECT summary, updated_at FROM advisor_session_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            preference_rows = connection.execute(
                "SELECT preference FROM advisor_pinned_preferences WHERE session_id = ? ORDER BY position ASC, rowid ASC",
                (session_id,),
            ).fetchall()
        if row is None:
            raise FileNotFoundError(f"Advisor session not found: {session_id}")
        return {
            "session_id": row["session_id"],
            "project_root": row["project_root"],
            "snapshot_digest": row["snapshot_digest"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "session_summary": summary_row["summary"] if summary_row is not None else "",
            "summary_updated_at": summary_row["updated_at"] if summary_row is not None else "",
            "pinned_user_preferences": [item["preference"] for item in preference_rows],
            "messages": [
                {
                    "sequence": int(item["sequence"]),
                    "role": item["role"],
                    "at": item["at"],
                    "payload": json.loads(item["payload_json"]),
                }
                for item in messages
            ],
        }

    def list_advisor_sessions(self, project_root: str, *, limit: int = 30) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT session_id, project_root, snapshot_digest, title, created_at, updated_at
                FROM advisor_sessions WHERE project_root = ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (project_root, max(1, min(200, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def append_advisor_message(self, session_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_advisor_id(session_id)
        if role not in {"user", "advisor"}:
            raise ValueError("advisor message role must be user or advisor")
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT 1 FROM advisor_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if existing is None:
                raise FileNotFoundError(f"Advisor session not found: {session_id}")
            sequence = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM advisor_messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT INTO advisor_messages (session_id, sequence, role, at, payload_json) VALUES (?, ?, ?, ?, ?)",
                (session_id, sequence, role, now, _json(payload)),
            )
            connection.execute("UPDATE advisor_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
        return {"sequence": sequence, "role": role, "at": now, "payload": payload}

    def save_advisor_memory(self, session_id: str, *, summary: str, preferences: list[str]) -> dict[str, Any]:
        _validate_advisor_id(session_id)
        now = _now()
        safe_summary = str(summary or "").strip()[:6000]
        safe_preferences = list(
            dict.fromkeys(str(item).strip()[:500] for item in preferences if str(item).strip())
        )[:30]
        with self._write_lock, self._connection() as connection:
            existing = connection.execute("SELECT 1 FROM advisor_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if existing is None:
                raise FileNotFoundError(f"Advisor session not found: {session_id}")
            if safe_summary:
                connection.execute(
                    """
                    INSERT INTO advisor_session_summaries (session_id, summary, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET summary = excluded.summary, updated_at = excluded.updated_at
                    """,
                    (session_id, safe_summary, now),
                )
            connection.execute("DELETE FROM advisor_pinned_preferences WHERE session_id = ?", (session_id,))
            for position, preference in enumerate(safe_preferences):
                connection.execute(
                    "INSERT INTO advisor_pinned_preferences (session_id, preference, position, updated_at) VALUES (?, ?, ?, ?)",
                    (session_id, preference, position, now),
                )
        return {"session_id": session_id, "session_summary": safe_summary, "pinned_user_preferences": safe_preferences, "updated_at": now}

    def save_delegation_policy(self, project_root: str, policy: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO delegation_policies (project_root, policy_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(project_root) DO UPDATE SET policy_json = excluded.policy_json, updated_at = excluded.updated_at
                """,
                (project_root, _json(policy), now),
            )
        return {"project_root": project_root, "policy": policy, "updated_at": now}

    def upsert_advisor_inbox(
        self,
        project_root: str,
        *,
        dedupe_key: str,
        kind: str,
        severity: str,
        title: str,
        message: str,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now()
        item_id = f"notice-{uuid.uuid4().hex[:16]}"
        with self._write_lock, self._connection() as connection:
            existing = connection.execute(
                "SELECT item_id FROM advisor_inbox WHERE project_root = ? AND dedupe_key = ?",
                (project_root, dedupe_key),
            ).fetchone()
            cursor = connection.execute(
                """
                INSERT INTO advisor_inbox (
                    item_id, project_root, dedupe_key, kind, severity, title, message,
                    action_json, created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '')
                ON CONFLICT(project_root, dedupe_key) DO UPDATE SET
                    kind = excluded.kind,
                    severity = excluded.severity,
                    title = excluded.title,
                    message = excluded.message,
                    action_json = excluded.action_json
                """,
                (item_id, project_root, dedupe_key, kind, severity, title, message, _json(action or {}), now),
            )
            row = connection.execute(
                "SELECT * FROM advisor_inbox WHERE project_root = ? AND dedupe_key = ?",
                (project_root, dedupe_key),
            ).fetchone()
        assert row is not None
        return {**self._advisor_inbox_row(row), "inserted": existing is None and bool(cursor.rowcount)}

    def advisor_inbox(self, project_root: str, *, unread_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        unread_clause = "AND read_at = ''" if unread_only else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM advisor_inbox WHERE project_root = ? {unread_clause} ORDER BY created_at DESC LIMIT ?",
                (project_root, max(1, min(500, int(limit)))),
            ).fetchall()
        return [self._advisor_inbox_row(row) for row in rows]

    def mark_advisor_inbox_read(self, item_id: str, *, read: bool = True) -> dict[str, Any]:
        with self._write_lock, self._connection() as connection:
            connection.execute("UPDATE advisor_inbox SET read_at = ? WHERE item_id = ?", (_now() if read else "", item_id))
            row = connection.execute("SELECT * FROM advisor_inbox WHERE item_id = ?", (item_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Advisor inbox item not found: {item_id}")
        return self._advisor_inbox_row(row)

    def reader_state(self, project_root: str) -> dict[str, Any]:
        with self._connection() as connection:
            position = connection.execute("SELECT * FROM reader_positions WHERE project_root = ?", (project_root,)).fetchone()
            bookmarks = connection.execute(
                "SELECT unit_id, created_at FROM reader_bookmarks WHERE project_root = ? ORDER BY created_at ASC",
                (project_root,),
            ).fetchall()
        return {
            "project_root": project_root,
            "position": {
                "unit_id": position["unit_id"],
                "scroll_ratio": float(position["scroll_ratio"]),
                "updated_at": position["updated_at"],
            } if position is not None else {"unit_id": "", "scroll_ratio": 0.0, "updated_at": ""},
            "bookmarks": [{"unit_id": row["unit_id"], "created_at": row["created_at"]} for row in bookmarks],
        }

    def save_reader_position(self, project_root: str, unit_id: str, scroll_ratio: float) -> dict[str, Any]:
        ratio = max(0.0, min(1.0, float(scroll_ratio)))
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO reader_positions (project_root, unit_id, scroll_ratio, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(project_root) DO UPDATE SET unit_id = excluded.unit_id,
                    scroll_ratio = excluded.scroll_ratio, updated_at = excluded.updated_at
                """,
                (project_root, unit_id, ratio, now),
            )
        return self.reader_state(project_root)

    def set_reader_bookmark(self, project_root: str, unit_id: str, enabled: bool) -> dict[str, Any]:
        with self._write_lock, self._connection() as connection:
            if enabled:
                connection.execute(
                    "INSERT OR IGNORE INTO reader_bookmarks (project_root, unit_id, created_at) VALUES (?, ?, ?)",
                    (project_root, unit_id, _now()),
                )
            else:
                connection.execute("DELETE FROM reader_bookmarks WHERE project_root = ? AND unit_id = ?", (project_root, unit_id))
        return self.reader_state(project_root)

    @staticmethod
    def _advisor_inbox_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "item_id": row["item_id"],
            "project_root": row["project_root"],
            "dedupe_key": row["dedupe_key"],
            "kind": row["kind"],
            "severity": row["severity"],
            "title": row["title"],
            "message": row["message"],
            "action": json.loads(row["action_json"]),
            "created_at": row["created_at"],
            "read_at": row["read_at"],
            "unread": not bool(row["read_at"]),
        }

    def read_delegation_policy(self, project_root: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT project_root, policy_json, updated_at FROM delegation_policies WHERE project_root = ?",
                (project_root,),
            ).fetchone()
        if row is None:
            return None
        return {"project_root": row["project_root"], "policy": json.loads(row["policy_json"]), "updated_at": row["updated_at"]}

    def create_autopilot_run(
        self,
        project_root: str,
        *,
        mode: str,
        runtime: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = f"autopilot-{uuid.uuid4().hex[:16]}"
        now = _now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO autopilot_runs (
                    run_id, project_root, mode, runtime, status, policy_json, created_at, updated_at, started_at
                ) VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (run_id, project_root, mode, runtime, _json(policy), now, now, now),
            )
            self._append_autopilot_event_tx(connection, run_id, "autopilot.started", {"mode": mode, "runtime": runtime})
        return self.read_autopilot_run(run_id)

    def read_autopilot_run(self, run_id: str) -> dict[str, Any]:
        _validate_autopilot_id(run_id)
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM autopilot_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self._autopilot_row(row)

    def latest_autopilot_run(self, project_root: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM autopilot_runs WHERE project_root = ? ORDER BY created_at DESC LIMIT 1",
                (project_root,),
            ).fetchone()
        return self._autopilot_row(row) if row is not None else None

    def update_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        _validate_autopilot_id(run_id)
        allowed = {
            "status", "current_route", "current_task_id", "tasks_completed", "failures",
            "consecutive_revisions", "estimated_cost", "last_error", "stop_reason", "finished_at",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.read_autopilot_run(run_id)
        values["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._write_lock, self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE autopilot_runs SET {assignments} WHERE run_id = ?",
                (*values.values(), run_id),
            )
            if not cursor.rowcount:
                raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self.read_autopilot_run(run_id)

    def advance_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        """Atomically advance a run after one task reaches its formal terminal state."""

        _validate_autopilot_id(run_id)
        allowed = {"failures", "consecutive_revisions", "estimated_cost", "last_error", "current_route", "current_task_id"}
        values = {key: value for key, value in changes.items() if key in allowed}
        values["updated_at"] = _now()
        assignments = ", ".join(["tasks_completed = tasks_completed + 1", *[f"{key} = ?" for key in values]])
        with self._write_lock, self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE autopilot_runs SET {assignments} WHERE run_id = ?",
                (*values.values(), run_id),
            )
            if not cursor.rowcount:
                raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self.read_autopilot_run(run_id)

    def acquire_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool:
        """Claim the cross-process controller lease for one autopilot run."""

        _validate_autopilot_id(run_id)
        owner = str(owner_id or "").strip()
        if not owner:
            raise ValueError("autopilot lease owner must not be empty")
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=max(30, lease_seconds))).isoformat()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM autopilot_leases WHERE lease_expires_at < ?", (now.isoformat(),))
            existing = connection.execute(
                "SELECT owner_id FROM autopilot_leases WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is not None and existing["owner_id"] != owner:
                return False
            connection.execute(
                """
                INSERT INTO autopilot_leases (run_id, owner_id, lease_expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    lease_expires_at = excluded.lease_expires_at,
                    updated_at = excluded.updated_at
                """,
                (run_id, owner, expires, now.isoformat()),
            )
            return True

    def renew_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool:
        """Extend a lease only when this controller still owns it."""

        _validate_autopilot_id(run_id)
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=max(30, lease_seconds))).isoformat()
        with self._write_lock, self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE autopilot_leases
                SET lease_expires_at = ?, updated_at = ?
                WHERE run_id = ? AND owner_id = ? AND lease_expires_at >= ?
                """,
                (expires, now.isoformat(), run_id, str(owner_id or ""), now.isoformat()),
            )
        return bool(cursor.rowcount)

    def release_autopilot_lease(self, run_id: str, owner_id: str) -> None:
        _validate_autopilot_id(run_id)
        with self._write_lock, self._connection() as connection:
            connection.execute(
                "DELETE FROM autopilot_leases WHERE run_id = ? AND owner_id = ?",
                (run_id, str(owner_id or "")),
            )

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        _validate_autopilot_id(run_id)
        with self._write_lock, self._connection() as connection:
            return self._append_autopilot_event_tx(connection, run_id, event, data)

    def autopilot_events_since(self, run_id: str, after: int = 0, *, limit: int = 300) -> list[dict[str, Any]]:
        _validate_autopilot_id(run_id)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT sequence, run_id, event_type, at, data_json FROM autopilot_events
                WHERE run_id = ? AND sequence > ? ORDER BY sequence ASC LIMIT ?
                """,
                (run_id, max(0, int(after)), max(1, min(2000, int(limit)))),
            ).fetchall()
        return [
            {"sequence": int(row["sequence"]), "run_id": row["run_id"], "event": row["event_type"], "at": row["at"], "data": json.loads(row["data_json"])}
            for row in rows
        ]

    def record_delegated_decision(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_autopilot_id(run_id)
        decision_id = f"decision-{uuid.uuid4().hex[:16]}"
        now = _now()
        record = {**payload, "decision_id": decision_id, "run_id": run_id, "created_at": now, "revoked_at": ""}
        with self._write_lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO delegated_decisions (decision_id, run_id, project_root, decision_json, created_at, revoked_at) VALUES (?, ?, ?, ?, ?, '')",
                (decision_id, run_id, str(payload.get("project_root") or ""), _json(record), now),
            )
            self._append_autopilot_event_tx(connection, run_id, "decision.delegated", {"decision_id": decision_id, "decision_type": payload.get("decision_type"), "selected_option": payload.get("selected_option")})
        return record

    def delegated_decisions(self, run_id: str) -> list[dict[str, Any]]:
        _validate_autopilot_id(run_id)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT decision_json, revoked_at FROM delegated_decisions WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        records = []
        for row in rows:
            payload = json.loads(row["decision_json"])
            payload["revoked_at"] = row["revoked_at"]
            records.append(payload)
        return records

    def recover_autopilot_runs(self) -> int:
        now = _now()
        with self._write_lock, self._connection() as connection:
            rows = connection.execute("SELECT run_id FROM autopilot_runs WHERE status IN ('running','stopping')").fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE autopilot_runs SET status = 'paused', stop_reason = 'application-restart', updated_at = ? WHERE run_id = ?",
                    (now, row["run_id"]),
                )
                self._append_autopilot_event_tx(connection, row["run_id"], "autopilot.recovered", {"status": "paused", "reason": "application-restart"})
        return len(rows)

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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    lease_owner TEXT NOT NULL DEFAULT '',
                    lease_expires_at TEXT NOT NULL DEFAULT '',
                    heartbeat_at TEXT NOT NULL DEFAULT '',
                    idempotency_key TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency_idx
                    ON jobs(idempotency_key) WHERE idempotency_key <> '';
                CREATE TABLE IF NOT EXISTS run_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    at TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                CREATE INDEX IF NOT EXISTS run_events_job_sequence_idx
                    ON run_events(job_id, sequence);
                CREATE TABLE IF NOT EXISTS project_locks (
                    lock_key TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_resources (
                    job_id TEXT PRIMARY KEY,
                    formal_project TEXT NOT NULL,
                    task_sandbox TEXT NOT NULL,
                    agent_session TEXT NOT NULL,
                    run_workspace TEXT NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS advisor_sessions (
                    session_id TEXT PRIMARY KEY,
                    project_root TEXT NOT NULL,
                    snapshot_digest TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS advisor_sessions_project_idx
                    ON advisor_sessions(project_root, updated_at);
                CREATE TABLE IF NOT EXISTS advisor_messages (
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(session_id, sequence),
                    FOREIGN KEY(session_id) REFERENCES advisor_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS advisor_session_summaries (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES advisor_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS advisor_pinned_preferences (
                    session_id TEXT NOT NULL,
                    preference TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, preference),
                    FOREIGN KEY(session_id) REFERENCES advisor_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS advisor_inbox (
                    item_id TEXT PRIMARY KEY,
                    project_root TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(project_root, dedupe_key)
                );
                CREATE INDEX IF NOT EXISTS advisor_inbox_project_idx
                    ON advisor_inbox(project_root, read_at, created_at);
                CREATE TABLE IF NOT EXISTS reader_positions (
                    project_root TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL,
                    scroll_ratio REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reader_bookmarks (
                    project_root TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(project_root, unit_id)
                );
                CREATE TABLE IF NOT EXISTS delegation_policies (
                    project_root TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autopilot_runs (
                    run_id TEXT PRIMARY KEY,
                    project_root TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    runtime TEXT NOT NULL,
                    status TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT '',
                    current_route TEXT NOT NULL DEFAULT '',
                    current_task_id TEXT NOT NULL DEFAULT '',
                    tasks_completed INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    consecutive_revisions INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    stop_reason TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS autopilot_runs_project_idx ON autopilot_runs(project_root, created_at);
                CREATE TABLE IF NOT EXISTS autopilot_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    at TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES autopilot_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS autopilot_events_run_idx ON autopilot_events(run_id, sequence);
                CREATE TABLE IF NOT EXISTS autopilot_leases (
                    run_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES autopilot_runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS delegated_decisions (
                    decision_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    project_root TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(run_id) REFERENCES autopilot_runs(run_id)
                );
                """
            )
            preference_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(advisor_pinned_preferences)").fetchall()
            }
            if "position" not in preference_columns:
                connection.execute(
                    "ALTER TABLE advisor_pinned_preferences ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")

    def _append_autopilot_event_tx(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        event: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if not event or any(char.isspace() for char in event):
            raise ValueError(f"invalid autopilot event: {event}")
        at = _now()
        cursor = connection.execute(
            "INSERT INTO autopilot_events (run_id, event_type, at, data_json) VALUES (?, ?, ?, ?)",
            (run_id, event, at, _json(_redact(data))),
        )
        return {"sequence": int(cursor.lastrowid), "run_id": run_id, "event": event, "at": at, "data": _redact(data)}

    @staticmethod
    def _autopilot_row(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["policy"] = json.loads(payload.pop("policy_json"))
        payload["tasks_completed"] = int(payload.get("tasks_completed") or 0)
        payload["failures"] = int(payload.get("failures") or 0)
        payload["consecutive_revisions"] = int(payload.get("consecutive_revisions") or 0)
        payload["estimated_cost"] = float(payload.get("estimated_cost") or 0)
        return payload

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level="DEFERRED")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

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


def _validate_job_id(job_id: str) -> None:
    if not job_id.startswith("job-") or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in job_id):
        raise ValueError(f"invalid worker job id: {job_id}")


def _validate_advisor_id(session_id: str) -> None:
    if not session_id.startswith("advisor-") or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in session_id
    ):
        raise ValueError(f"invalid advisor session id: {session_id}")


def _validate_autopilot_id(run_id: str) -> None:
    if not run_id.startswith("autopilot-") or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in run_id
    ):
        raise ValueError(f"invalid autopilot run id: {run_id}")


def _public_request(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if "key" not in key.lower() and "secret" not in key.lower()}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(token in key.lower() for token in ("secret", "token", "password", "api_key")) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
