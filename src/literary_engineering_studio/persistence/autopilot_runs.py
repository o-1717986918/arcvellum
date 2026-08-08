"""Autopilot run, lease, decision, and event persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any
import uuid

from .primitives import _json, _now, _redact, _validate_autopilot_id
from .sqlite_uow import SqliteUnitOfWork


class AutopilotRepository:
    """Persist autopilot lifecycle state through an explicit unit of work."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

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
        with self._uow.write() as connection:
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
        with self._uow.read() as connection:
            row = connection.execute("SELECT * FROM autopilot_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self._autopilot_row(row)

    def latest_autopilot_run(self, project_root: str) -> dict[str, Any] | None:
        with self._uow.read() as connection:
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
            "route_index", "progress_fingerprint", "stalled_cycles", "last_progress_at",
            "last_recovery_at",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.read_autopilot_run(run_id)
        values["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._uow.write() as connection:
            cursor = connection.execute(
                f"UPDATE autopilot_runs SET {assignments} WHERE run_id = ?",
                (*values.values(), run_id),
            )
            if not cursor.rowcount:
                raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self.read_autopilot_run(run_id)

    def update_autopilot_run_policy(self, run_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        """Renew the immutable run policy after an explicit user authorization.

        A paused run evaluates its own stored policy, not the project's default
        policy.  Without this write, changing a limit in the interface looks
        successful but a resumed controller immediately stops on the old cap.
        """

        _validate_autopilot_id(run_id)
        with self._uow.write() as connection:
            cursor = connection.execute(
                "UPDATE autopilot_runs SET policy_json = ?, mode = ?, updated_at = ? WHERE run_id = ?",
                (_json(policy), str(policy.get("mode") or "collaborative"), _now(), run_id),
            )
            if not cursor.rowcount:
                raise FileNotFoundError(f"Autopilot run not found: {run_id}")
        return self.read_autopilot_run(run_id)

    def advance_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        """Atomically advance a run after one task reaches its formal terminal state."""

        _validate_autopilot_id(run_id)
        allowed = {
            "failures", "consecutive_revisions", "estimated_cost", "last_error",
            "current_route", "current_task_id", "route_index", "progress_fingerprint",
            "stalled_cycles", "last_progress_at", "last_recovery_at",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        values["updated_at"] = _now()
        assignments = ", ".join(["tasks_completed = tasks_completed + 1", *[f"{key} = ?" for key in values]])
        with self._uow.write() as connection:
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
        with self._uow.write(immediate=True) as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.write() as connection:
            connection.execute(
                "DELETE FROM autopilot_leases WHERE run_id = ? AND owner_id = ?",
                (run_id, str(owner_id or "")),
            )

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        _validate_autopilot_id(run_id)
        with self._uow.write() as connection:
            return self._append_autopilot_event_tx(connection, run_id, event, data)

    def autopilot_events_since(self, run_id: str, after: int = 0, *, limit: int = 300) -> list[dict[str, Any]]:
        _validate_autopilot_id(run_id)
        with self._uow.read() as connection:
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
        with self._uow.write() as connection:
            connection.execute(
                "INSERT INTO delegated_decisions (decision_id, run_id, project_root, decision_json, created_at, revoked_at) VALUES (?, ?, ?, ?, ?, '')",
                (decision_id, run_id, str(payload.get("project_root") or ""), _json(record), now),
            )
            self._append_autopilot_event_tx(connection, run_id, "decision.delegated", {"decision_id": decision_id, "decision_type": payload.get("decision_type"), "selected_option": payload.get("selected_option")})
        return record

    def delegated_decisions(self, run_id: str) -> list[dict[str, Any]]:
        _validate_autopilot_id(run_id)
        with self._uow.read() as connection:
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
        with self._uow.write() as connection:
            rows = connection.execute("SELECT run_id FROM autopilot_runs WHERE status IN ('running','stopping')").fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE autopilot_runs SET status = 'paused', stop_reason = 'application-restart', updated_at = ? WHERE run_id = ?",
                    (now, row["run_id"]),
                )
                self._append_autopilot_event_tx(connection, row["run_id"], "autopilot.recovered", {"status": "paused", "reason": "application-restart"})
        return len(rows)

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
        payload["route_index"] = int(payload.get("route_index") or 0)
        payload["stalled_cycles"] = int(payload.get("stalled_cycles") or 0)
        return payload
