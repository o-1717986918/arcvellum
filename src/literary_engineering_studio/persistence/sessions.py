"""Advisor, Agent-session, inbox, delegation, and reader persistence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .primitives import _json, _now, _validate_advisor_id, _validate_agent_session_id
from .sqlite_uow import SqliteUnitOfWork


class SessionRepository:
    """Persist user and Agent sessions through an explicit unit of work."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def create_advisor_session(self, project_root: str, snapshot_digest: str, *, title: str = "项目问答") -> dict[str, Any]:
        session_id = f"advisor-{uuid.uuid4().hex[:16]}"
        now = _now()
        with self._uow.write() as connection:
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
        with self._uow.read() as connection:
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
        with self._uow.read() as connection:
            rows = connection.execute(
                """
                SELECT session_id, project_root, snapshot_digest, title, created_at, updated_at
                FROM advisor_sessions WHERE project_root = ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (project_root, max(1, min(200, int(limit)))),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_agent_session(
        self,
        session_id: str,
        *,
        project_root: str,
        role: str,
        runtime: str,
        model: str = "",
        status: str = "running",
        task_id: str = "",
        route: str = "",
        controller_id: str = "",
        last_event: str = "",
        last_message: str = "",
        retry_count: int = 0,
        context_ledger_id: str = "",
        context_ledger_digest: str = "",
    ) -> dict[str, Any]:
        """Create or refresh the public lifecycle record for one real Agent session."""

        session = _validate_agent_session_id(session_id)
        normalized_status = str(status or "running").strip().lower()
        if normalized_status not in {
            "queued", "running", "waiting", "waiting_human", "idle",
            "complete", "failed", "cancelled", "stopped",
        }:
            raise ValueError(f"unsupported Agent session status: {status}")
        now = _now()
        terminal = normalized_status in {"complete", "failed", "cancelled", "stopped"}
        with self._uow.write() as connection:
            existing = connection.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?",
                (session,),
            ).fetchone()
            started_at = str(existing["started_at"]) if existing is not None else now
            event_count = int(existing["event_count"] or 0) + (1 if last_event else 0) if existing is not None else (1 if last_event else 0)
            values = _merged_session_values(
                existing,
                project_root=project_root,
                role=role,
                runtime=runtime,
                model=model,
                task_id=task_id,
                route=route,
                controller_id=controller_id,
                last_message=last_message,
                retry_count=retry_count,
                context_ledger_id=context_ledger_id,
                context_ledger_digest=context_ledger_digest,
            )
            _write_agent_session(
                connection,
                session=session,
                status=normalized_status,
                started_at=started_at,
                now=now,
                terminal=terminal,
                event_count=event_count,
                last_event=str(last_event or "")[:120],
                values=values,
            )
        return self.read_agent_session(session)

    def read_agent_session(self, session_id: str) -> dict[str, Any]:
        session = _validate_agent_session_id(session_id)
        with self._uow.read() as connection:
            row = connection.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?",
                (session,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Agent session not found: {session}")
        return self._agent_session_row(row)

    def list_agent_sessions(
        self,
        project_root: str,
        *,
        include_finished: bool = True,
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        finished_clause = "" if include_finished else "AND status NOT IN ('complete','failed','cancelled','stopped')"
        with self._uow.read() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM agent_sessions
                WHERE project_root = ? {finished_clause}
                ORDER BY
                    CASE WHEN finished_at = '' THEN 0 ELSE 1 END ASC,
                    updated_at DESC
                LIMIT ?
                """,
                (str(project_root or ""), max(1, min(200, int(limit)))),
            ).fetchall()
        return [self._agent_session_row(row) for row in rows]

    def append_advisor_message(self, session_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_advisor_id(session_id)
        if role not in {"user", "advisor"}:
            raise ValueError("advisor message role must be user or advisor")
        now = _now()
        with self._uow.write(immediate=True) as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.read() as connection:
            rows = connection.execute(
                f"SELECT * FROM advisor_inbox WHERE project_root = ? {unread_clause} ORDER BY created_at DESC LIMIT ?",
                (project_root, max(1, min(500, int(limit)))),
            ).fetchall()
        return [self._advisor_inbox_row(row) for row in rows]

    def mark_advisor_inbox_read(self, item_id: str, *, read: bool = True) -> dict[str, Any]:
        with self._uow.write() as connection:
            connection.execute("UPDATE advisor_inbox SET read_at = ? WHERE item_id = ?", (_now() if read else "", item_id))
            row = connection.execute("SELECT * FROM advisor_inbox WHERE item_id = ?", (item_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Advisor inbox item not found: {item_id}")
        return self._advisor_inbox_row(row)

    def reader_state(self, project_root: str) -> dict[str, Any]:
        with self._uow.read() as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.write() as connection:
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
        with self._uow.read() as connection:
            row = connection.execute(
                "SELECT project_root, policy_json, updated_at FROM delegation_policies WHERE project_root = ?",
                (project_root,),
            ).fetchone()
        if row is None:
            return None
        return {"project_root": row["project_root"], "policy": json.loads(row["policy_json"]), "updated_at": row["updated_at"]}

    @staticmethod
    def _agent_session_row(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["event_count"] = int(payload.get("event_count") or 0)
        payload["retry_count"] = int(payload.get("retry_count") or 0)
        return payload
def _merged_session_values(existing, **values: Any) -> dict[str, Any]:
    limits = {
        "project_root": None,
        "role": 40,
        "runtime": 80,
        "model": 160,
        "task_id": 180,
        "route": 80,
        "controller_id": 180,
        "last_message": 600,
        "context_ledger_id": 96,
        "context_ledger_digest": 64,
    }
    result = {
        key: _preserved_text(existing, key, values.get(key), limit)
        for key, limit in limits.items()
    }
    result["retry_count"] = max(
        _existing_int(existing, "retry_count"),
        max(0, int(values.get("retry_count") or 0)),
    )
    return result


def _preserved_text(existing, key: str, value: Any, limit: int | None) -> str:
    selected = value
    if not selected and existing is not None:
        selected = existing[key]
    text = str(selected or "")
    return text[:limit] if limit is not None else text


def _existing_int(existing, key: str) -> int:
    return max(0, int(existing[key] or 0)) if existing is not None else 0


def _write_agent_session(
    connection,
    *,
    session: str,
    status: str,
    started_at: str,
    now: str,
    terminal: bool,
    event_count: int,
    last_event: str,
    values: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO agent_sessions (
            session_id, project_root, role, runtime, model, status,
            task_id, route, controller_id, started_at, updated_at,
            finished_at, event_count, last_event, last_message, retry_count,
            context_ledger_id, context_ledger_digest
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            project_root = excluded.project_root,
            role = excluded.role,
            runtime = excluded.runtime,
            model = excluded.model,
            status = excluded.status,
            task_id = excluded.task_id,
            route = excluded.route,
            controller_id = excluded.controller_id,
            updated_at = excluded.updated_at,
            finished_at = excluded.finished_at,
            event_count = excluded.event_count,
            last_event = excluded.last_event,
            last_message = excluded.last_message,
            retry_count = excluded.retry_count,
            context_ledger_id = excluded.context_ledger_id,
            context_ledger_digest = excluded.context_ledger_digest
        """,
        (
            session,
            values["project_root"],
            values["role"],
            values["runtime"],
            values["model"],
            status,
            values["task_id"],
            values["route"],
            values["controller_id"],
            started_at,
            now,
            now if terminal else "",
            event_count,
            last_event,
            values["last_message"],
            values["retry_count"],
            values["context_ledger_id"],
            values["context_ledger_digest"],
        ),
    )
