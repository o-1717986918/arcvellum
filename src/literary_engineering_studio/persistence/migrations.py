"""Small additive SQLite migrations shared by the durable Studio store."""

from __future__ import annotations

import sqlite3


def ensure_additive_columns(connection: sqlite3.Connection) -> None:
    preference_columns = _columns(connection, "advisor_pinned_preferences")
    if "position" not in preference_columns:
        connection.execute(
            "ALTER TABLE advisor_pinned_preferences "
            "ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
        )
    autopilot_columns = _columns(connection, "autopilot_runs")
    autopilot_additions = {
        "route_index": "INTEGER NOT NULL DEFAULT 0",
        "progress_fingerprint": "TEXT NOT NULL DEFAULT ''",
        "stalled_cycles": "INTEGER NOT NULL DEFAULT 0",
        "last_progress_at": "TEXT NOT NULL DEFAULT ''",
        "last_recovery_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, declaration in autopilot_additions.items():
        if name not in autopilot_columns:
            connection.execute(f"ALTER TABLE autopilot_runs ADD COLUMN {name} {declaration}")
    if "operation" not in _columns(connection, "archive_asset_transactions"):
        connection.execute(
            "ALTER TABLE archive_asset_transactions "
            "ADD COLUMN operation TEXT NOT NULL DEFAULT 'replace'"
        )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if table not in {
        "advisor_pinned_preferences",
        "autopilot_runs",
        "archive_asset_transactions",
    }:
        raise ValueError(f"unsupported migration table: {table}")
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
