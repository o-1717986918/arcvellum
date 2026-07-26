"""Durable metadata index for adaptive creative plans and revisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .creative_plan_activation import (
    apply_creative_plan_activation,
    capture_active_projection,
    restore_active_projection,
)
from .creative_plan_artifacts import verify_indexed_plan_artifacts
from .creative_plan_events import append_creative_plan_event_tx
from .creative_plan_primitives import positive_revision, project_key, validate_plan_id
from .primitives import _json, _now


CREATIVE_PLAN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS creative_plans (
    plan_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    status TEXT NOT NULL,
    active_revision INTEGER NOT NULL DEFAULT 0,
    base_project_fingerprint TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS creative_plans_project_idx
    ON creative_plans(project_root, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS creative_plans_one_active_per_project_idx
    ON creative_plans(project_root) WHERE status = 'active';
CREATE TABLE IF NOT EXISTS creative_plan_revisions (
    plan_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    candidate_json TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    compiled_json TEXT NOT NULL,
    lint_json TEXT NOT NULL,
    simulation_json TEXT NOT NULL,
    review_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    artifact_state TEXT NOT NULL DEFAULT 'reserved',
    created_at TEXT NOT NULL,
    PRIMARY KEY(plan_id, revision),
    FOREIGN KEY(plan_id) REFERENCES creative_plans(plan_id)
);
"""


class CreativePlanStoreMixin:
    """Methods require the host JobStore connection and write-lock protocol."""

    def reserve_creative_plan_revision(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_revision_record(record)
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            plan = connection.execute(
                "SELECT * FROM creative_plans WHERE plan_id = ?",
                (normalized["plan_id"],),
            ).fetchone()
            if plan is None:
                _insert_plan(connection, normalized)
            else:
                _validate_existing_plan(dict(plan), normalized)
            existing = connection.execute(
                """
                SELECT * FROM creative_plan_revisions
                WHERE plan_id = ? AND revision = ?
                """,
                (normalized["plan_id"], normalized["revision"]),
            ).fetchone()
            if existing is not None:
                current = _revision_row(existing)
                if current["digest"] != normalized["digest"]:
                    raise ValueError("creative plan revision conflicts with an existing digest")
                return current
            _insert_revision(connection, normalized)
            append_creative_plan_event_tx(
                connection,
                normalized["plan_id"],
                normalized["revision"],
                "plan.revision.reserved",
                {"digest": normalized["digest"], "status": normalized["status"]},
            )
        return self.read_creative_plan_revision(
            normalized["plan_id"],
            normalized["revision"],
        )

    def finalize_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
        *,
        digest: str,
    ) -> dict[str, Any]:
        validate_plan_id(plan_id)
        revision = positive_revision(revision)
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT revisions.*, plans.project_root
                FROM creative_plan_revisions AS revisions
                JOIN creative_plans AS plans ON plans.plan_id = revisions.plan_id
                WHERE revisions.plan_id = ? AND revisions.revision = ?
                """,
                (plan_id, revision),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"creative plan revision not found: {plan_id}@{revision}")
            if str(row["digest"]) != digest:
                raise ValueError("creative plan revision finalize digest mismatch")
            revision_payload = _revision_row(row)
            project_root = str(revision_payload.pop("project_root"))
            verify_indexed_plan_artifacts(project_root, revision_payload)
            if str(row["artifact_state"]) != "ready":
                connection.execute(
                    """
                    UPDATE creative_plan_revisions SET artifact_state = 'ready'
                    WHERE plan_id = ? AND revision = ?
                    """,
                    (plan_id, revision),
                )
                append_creative_plan_event_tx(
                    connection,
                    plan_id,
                    revision,
                    "plan.revision.ready",
                    {"digest": digest},
                )
        return self.read_creative_plan_revision(plan_id, revision)

    def read_creative_plan(self, plan_id: str) -> dict[str, Any]:
        validate_plan_id(plan_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM creative_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"creative plan not found: {plan_id}")
        return _plan_row(row)

    def list_creative_plans(
        self,
        project_root: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        project = project_key(project_root)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM creative_plans
                WHERE project_root = ?
                ORDER BY updated_at DESC, plan_id DESC LIMIT ?
                """,
                (project, max(1, min(1000, int(limit)))),
            ).fetchall()
        return [_plan_row(row) for row in rows]

    def read_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
    ) -> dict[str, Any]:
        validate_plan_id(plan_id)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM creative_plan_revisions
                WHERE plan_id = ? AND revision = ?
                """,
                (plan_id, positive_revision(revision)),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"creative plan revision not found: {plan_id}@{revision}")
        return _revision_row(row)

    def activate_creative_plan(
        self,
        plan_id: str,
        revision: int,
        *,
        expected_active_revision: int,
        current_project_fingerprint: str,
        verified_revision_digest: str,
        active_plan_path: Path,
        active_plan_payload: dict[str, Any],
    ) -> dict[str, Any]:
        validate_plan_id(plan_id)
        requested_revision = positive_revision(revision)
        with self._write_lock:
            self._activate_creative_plan_transaction(
                plan_id,
                requested_revision,
                expected_active_revision=expected_active_revision,
                current_project_fingerprint=current_project_fingerprint,
                verified_revision_digest=verified_revision_digest,
                active_plan_path=active_plan_path,
                active_plan_payload=active_plan_payload,
            )
        return self.read_creative_plan(plan_id)

    def _activate_creative_plan_transaction(
        self,
        plan_id: str,
        requested_revision: int,
        *,
        expected_active_revision: int,
        current_project_fingerprint: str,
        verified_revision_digest: str,
        active_plan_path: Path,
        active_plan_payload: dict[str, Any],
    ) -> None:
        connection = self._connect()
        previous: str | None = None
        projection_touched = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            plan, revision = _activation_records(
                connection,
                plan_id,
                requested_revision,
            )
            _validate_activation_request(
                plan,
                revision,
                expected_active_revision=expected_active_revision,
                current_project_fingerprint=current_project_fingerprint,
                verified_revision_digest=verified_revision_digest,
            )
            previous = capture_active_projection(active_plan_path)
            projection_touched = True
            apply_creative_plan_activation(
                connection,
                plan=plan,
                revision=revision,
                requested_revision=requested_revision,
                expected_active_revision=expected_active_revision,
                verified_revision_digest=verified_revision_digest,
                current_project_fingerprint=current_project_fingerprint,
                active_plan_path=active_plan_path,
                active_plan_payload=active_plan_payload,
            )
            connection.commit()
        except Exception:
            try:
                if projection_touched:
                    restore_active_projection(active_plan_path, previous)
            finally:
                connection.rollback()
            raise
        finally:
            connection.close()


def _activation_records(
    connection,
    plan_id: str,
    revision: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_row = connection.execute(
        "SELECT * FROM creative_plans WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    revision_row = connection.execute(
        """
        SELECT * FROM creative_plan_revisions
        WHERE plan_id = ? AND revision = ?
        """,
        (plan_id, revision),
    ).fetchone()
    if plan_row is None or revision_row is None:
        raise FileNotFoundError(
            f"creative plan revision not found: {plan_id}@{revision}"
        )
    return dict(plan_row), _revision_row(revision_row)


def _validate_activation_request(
    plan: dict[str, Any],
    revision: dict[str, Any],
    *,
    expected_active_revision: int,
    current_project_fingerprint: str,
    verified_revision_digest: str,
) -> None:
    if int(plan["active_revision"]) != int(expected_active_revision):
        raise RuntimeError("creative plan active revision changed concurrently")
    if str(plan["base_project_fingerprint"]) != current_project_fingerprint:
        raise RuntimeError("creative plan is stale for the current project revision")
    if revision["digest"] != verified_revision_digest:
        raise RuntimeError("creative plan audit files have not been verified")
    if revision["artifact_state"] != "ready":
        raise RuntimeError("creative plan audit artifacts are not ready")


def _normalize_revision_record(record: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(record.get("plan_id") or "").strip()
    validate_plan_id(plan_id)
    _validate_initial_status(record.get("status"))
    normalized = {
        "plan_id": plan_id,
        "revision": positive_revision(record.get("revision")),
        "project_root": project_key(str(record.get("project_root") or "")),
        "scope_kind": str(record.get("scope_kind") or "").strip(),
        "scope_key": str(record.get("scope_key") or "").strip(),
        "status": "shadow",
        "base_project_fingerprint": str(
            record.get("base_project_fingerprint") or ""
        ).strip(),
        "policy": _mapping(record.get("policy")),
        "candidate": _mapping(record.get("candidate")),
        "normalized": _mapping(record.get("normalized")),
        "compiled": _mapping(record.get("compiled")),
        "lint": _mapping(record.get("lint")),
        "simulation": _mapping(record.get("simulation")),
        "review": _mapping(record.get("review")),
        "digest": _validated_digest(record.get("digest")),
        "created_at": str(record.get("created_at") or _now()),
    }
    if not normalized["scope_kind"] or not normalized["scope_key"]:
        raise ValueError("creative plan scope is required")
    if not normalized["base_project_fingerprint"]:
        raise ValueError("creative plan project fingerprint is required")
    return normalized


def _validate_initial_status(value: object) -> None:
    if str(value or "shadow").strip() != "shadow":
        raise ValueError("creative plan status is machine-owned and must start as shadow")


def _validated_digest(value: object) -> str:
    digest = str(value or "").strip()
    if len(digest) != 64 or any(
        char not in "0123456789abcdef" for char in digest
    ):
        raise ValueError("creative plan revision digest must be lowercase sha256")
    return digest


def _insert_plan(connection, record: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO creative_plans (
            plan_id, project_root, scope_kind, scope_key, status,
            active_revision, base_project_fingerprint, policy_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            record["plan_id"],
            record["project_root"],
            record["scope_kind"],
            record["scope_key"],
            record["status"],
            record["base_project_fingerprint"],
            _json(record["policy"]),
            record["created_at"],
            record["created_at"],
        ),
    )


def _insert_revision(connection, record: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO creative_plan_revisions (
            plan_id, revision, candidate_json, normalized_json, compiled_json,
            lint_json, simulation_json, review_json, digest, artifact_state, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
        """,
        (
            record["plan_id"],
            record["revision"],
            _json(record["candidate"]),
            _json(record["normalized"]),
            _json(record["compiled"]),
            _json(record["lint"]),
            _json(record["simulation"]),
            _json(record["review"]),
            record["digest"],
            record["created_at"],
        ),
    )


def _validate_existing_plan(plan: dict[str, Any], record: dict[str, Any]) -> None:
    identity = ("project_root", "scope_kind", "scope_key", "base_project_fingerprint")
    if any(str(plan[field]) != str(record[field]) for field in identity):
        raise ValueError("creative plan identity conflicts with the existing index")


def _plan_row(row) -> dict[str, Any]:
    payload = dict(row)
    payload["policy"] = json.loads(str(payload.pop("policy_json") or "{}"))
    return payload


def _revision_row(row) -> dict[str, Any]:
    payload = dict(row)
    for name in ("candidate", "normalized", "compiled", "lint", "simulation", "review"):
        payload[name] = json.loads(str(payload.pop(f"{name}_json") or "{}"))
    return payload


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
