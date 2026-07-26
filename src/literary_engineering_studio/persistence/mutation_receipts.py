"""Durable metadata index for machine-owned Worker mutation receipts."""

from __future__ import annotations

import json
from typing import Any

from ..observability.mutation_receipts import (
    MUTATION_RECEIPT_SCHEMA,
    parse_mutation_receipt,
)


MUTATION_RECEIPT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mutation_receipts (
    receipt_id TEXT PRIMARY KEY,
    change_group_id TEXT NOT NULL,
    project_root TEXT NOT NULL,
    project_key TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_revision INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    context_ledger_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    base_sha256 TEXT NOT NULL DEFAULT '',
    result_sha256 TEXT NOT NULL DEFAULT '',
    preflight_status TEXT NOT NULL,
    writeback_status TEXT NOT NULL,
    formal_effect TEXT NOT NULL,
    created_at TEXT NOT NULL,
    digest TEXT NOT NULL,
    receipt_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS mutation_receipts_project_idx
    ON mutation_receipts(project_root, created_at);
CREATE INDEX IF NOT EXISTS mutation_receipts_task_idx
    ON mutation_receipts(task_id, run_id, created_at);
CREATE INDEX IF NOT EXISTS mutation_receipts_session_idx
    ON mutation_receipts(session_id, created_at);
CREATE INDEX IF NOT EXISTS mutation_receipts_plan_idx
    ON mutation_receipts(plan_id, plan_revision, created_at);
CREATE INDEX IF NOT EXISTS mutation_receipts_group_idx
    ON mutation_receipts(change_group_id, created_at);
"""


class MutationReceiptStoreMixin:
    def record_mutation_receipt(
        self,
        project_root: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        receipt = parse_mutation_receipt(payload)
        project = str(project_root or "").strip()
        if not project:
            raise ValueError("mutation receipt project_root is required")
        canonical = receipt.as_dict()
        with self._write_lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT project_root, digest, receipt_json FROM mutation_receipts WHERE receipt_id = ?",
                (receipt.receipt_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["project_root"]) != project:
                    raise ValueError("mutation receipt belongs to a different project")
                if str(existing["digest"]) != receipt.digest:
                    raise ValueError("mutation receipt conflicts with an existing digest")
                return json.loads(str(existing["receipt_json"]))
            connection.execute(
                """
                INSERT INTO mutation_receipts (
                    receipt_id, change_group_id, project_root, project_key,
                    plan_id, plan_revision, node_id, task_id, run_id, session_id,
                    context_ledger_id, action, target, base_sha256, result_sha256,
                    preflight_status, writeback_status, formal_effect, created_at,
                    digest, receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.receipt_id,
                    receipt.change_group_id,
                    project,
                    receipt.project_key,
                    receipt.plan_id,
                    receipt.plan_revision,
                    receipt.node_id,
                    receipt.task_id,
                    receipt.run_id,
                    receipt.session_id,
                    receipt.context_ledger_id,
                    receipt.action.value,
                    receipt.target,
                    receipt.base_sha256,
                    receipt.result_sha256,
                    receipt.preflight_status,
                    receipt.writeback_status,
                    receipt.formal_effect.value,
                    receipt.created_at,
                    receipt.digest,
                    json.dumps(canonical, ensure_ascii=False, sort_keys=True),
                ),
            )
        return canonical

    def read_mutation_receipt(self, receipt_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT receipt_json FROM mutation_receipts WHERE receipt_id = ?",
                (_validate_receipt_id(receipt_id),),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"mutation receipt not found: {receipt_id}")
        return json.loads(str(row["receipt_json"]))

    def list_mutation_receipts(
        self,
        project_root: str,
        *,
        task_id: str = "",
        run_id: str = "",
        session_id: str = "",
        plan_id: str = "",
        change_group_id: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses = ["project_root = ?"]
        values: list[object] = [str(project_root or "")]
        for column, value in (
            ("task_id", task_id),
            ("run_id", run_id),
            ("session_id", session_id),
            ("plan_id", plan_id),
            ("change_group_id", change_group_id),
        ):
            if str(value or "").strip():
                clauses.append(f"{column} = ?")
                values.append(str(value).strip())
        values.append(max(1, min(2000, int(limit))))
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT receipt_json FROM mutation_receipts
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at ASC, receipt_id ASC LIMIT ?
                """,
                tuple(values),
            ).fetchall()
        return [json.loads(str(row["receipt_json"])) for row in rows]


def _validate_receipt_id(value: str) -> str:
    receipt_id = str(value or "").strip()
    if not receipt_id.startswith("receipt-") or len(receipt_id) > 96:
        raise ValueError(f"invalid mutation receipt id: {value}")
    return receipt_id
