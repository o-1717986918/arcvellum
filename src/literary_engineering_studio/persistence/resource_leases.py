"""Durable resource-claim leases for bounded same-project concurrency."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from .sqlite_uow import SqliteUnitOfWork


RESOURCE_LEASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS resource_leases (
    lease_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_node_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    lease_owner TEXT NOT NULL,
    claim_json TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS resource_leases_project_idx
    ON resource_leases(project_id, lease_expires_at);
CREATE INDEX IF NOT EXISTS resource_leases_job_idx
    ON resource_leases(job_id);
"""


class ResourceLeaseRepository:
    """Persist leases while delegating domain conflicts to one callback."""

    def __init__(self, uow: SqliteUnitOfWork):
        self._uow = uow

    def acquire_resource_lease(
        self,
        claim: dict[str, Any],
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
        conflicts: Callable[[dict[str, Any], dict[str, Any]], bool],
    ) -> str:
        project_id, task_node_id = _claim_identity(claim)
        if not job_id.strip() or not lease_owner.strip():
            raise ValueError("resource lease job_id and lease_owner are required")
        lease_id = _lease_id(job_id, task_node_id)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(30, int(lease_seconds)))
        encoded = _canonical(claim)
        with self._uow.write(immediate=True) as connection:
            connection.execute(
                "DELETE FROM resource_leases WHERE lease_expires_at < ?",
                (now.isoformat(),),
            )
            rows = connection.execute(
                "SELECT lease_id, claim_json FROM resource_leases WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            for row in rows:
                if str(row["lease_id"]) == lease_id:
                    if str(row["claim_json"]) != encoded:
                        raise RuntimeError(
                            "resource lease identity was reused with another claim"
                        )
                    break
                other = json.loads(str(row["claim_json"]))
                if conflicts(claim, other):
                    return ""
            connection.execute(
                """
                INSERT INTO resource_leases (
                    lease_id, project_id, task_node_id, job_id, lease_owner,
                    claim_json, lease_expires_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_id) DO UPDATE SET
                    lease_owner = excluded.lease_owner,
                    lease_expires_at = excluded.lease_expires_at,
                    updated_at = excluded.updated_at
                """,
                (
                    lease_id,
                    project_id,
                    task_node_id,
                    job_id,
                    lease_owner,
                    encoded,
                    expires.isoformat(),
                    now.isoformat(),
                ),
            )
        return lease_id

    def renew_resource_lease(
        self,
        lease_id: str,
        *,
        job_id: str,
        lease_owner: str,
        lease_seconds: int,
    ) -> bool:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(30, int(lease_seconds)))
        with self._uow.write() as connection:
            cursor = connection.execute(
                """
                UPDATE resource_leases
                SET lease_expires_at = ?, updated_at = ?
                WHERE lease_id = ? AND job_id = ? AND lease_owner = ?
                """,
                (
                    expires.isoformat(),
                    now.isoformat(),
                    lease_id,
                    job_id,
                    lease_owner,
                ),
            )
        return cursor.rowcount == 1

    def heartbeat_resource_execution(
        self,
        job_id: str,
        lease_owner: str,
        lease_id: str,
        *,
        lease_seconds: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        job_expires = now + timedelta(seconds=max(10, int(lease_seconds)))
        resource_expires = now + timedelta(seconds=max(30, int(lease_seconds) * 2))
        with self._uow.write(immediate=True) as connection:
            job = connection.execute(
                """
                UPDATE jobs SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                WHERE job_id = ? AND lease_owner = ?
                    AND status IN ('running', 'stopping')
                """,
                (
                    now.isoformat(),
                    job_expires.isoformat(),
                    now.isoformat(),
                    job_id,
                    lease_owner,
                ),
            )
            if job.rowcount != 1:
                raise RuntimeError(
                    f"job lease is not owned by {lease_owner}: {job_id}"
                )
            lease = connection.execute(
                """
                UPDATE resource_leases
                SET lease_expires_at = ?, updated_at = ?
                WHERE lease_id = ? AND job_id = ? AND lease_owner = ?
                """,
                (
                    resource_expires.isoformat(),
                    now.isoformat(),
                    lease_id,
                    job_id,
                    lease_owner,
                ),
            )
            if lease.rowcount != 1:
                raise RuntimeError(
                    f"resource execution lease is not owned by {lease_owner}: {lease_id}"
                )

    def release_resource_lease(self, lease_id: str, *, job_id: str) -> bool:
        with self._uow.write() as connection:
            cursor = connection.execute(
                "DELETE FROM resource_leases WHERE lease_id = ? AND job_id = ?",
                (lease_id, job_id),
            )
        return cursor.rowcount == 1

    def list_resource_leases(self, project_id: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM resource_leases"
        parameters: tuple[object, ...] = ()
        if project_id.strip():
            query += " WHERE project_id = ?"
            parameters = (project_id,)
        query += " ORDER BY updated_at, lease_id"
        with self._uow.read() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                **dict(row),
                "claim": json.loads(str(row["claim_json"])),
            }
            for row in rows
        ]


def _claim_identity(claim: dict[str, Any]) -> tuple[str, str]:
    project_id = str(claim.get("project_id") or "").strip()
    task_node_id = str(claim.get("task_node_id") or "").strip()
    if not project_id or not task_node_id:
        raise ValueError("resource claim project_id and task_node_id are required")
    return project_id, task_node_id


def _lease_id(job_id: str, task_node_id: str) -> str:
    digest = hashlib.sha256(f"{job_id}|{task_node_id}".encode("utf-8")).hexdigest()
    return f"resource-{digest[:24]}"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
