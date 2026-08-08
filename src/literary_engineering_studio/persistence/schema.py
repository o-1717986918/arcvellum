"""SQLite DDL assembly and additive migration entrypoint."""

from __future__ import annotations

import sqlite3

from .asset_revisions import ASSET_REVISION_SCHEMA_SQL
from .asset_transactions import ASSET_TRANSACTION_SCHEMA_SQL
from .creative_plans import CREATIVE_PLAN_SCHEMA_SQL
from .creative_plan_events import CREATIVE_PLAN_EVENT_SCHEMA_SQL
from .context_ledgers import CONTEXT_LEDGER_SCHEMA_SQL
from .migrations import ensure_additive_columns
from .mutation_receipts import MUTATION_RECEIPT_SCHEMA_SQL
from .primitives import DATABASE_SCHEMA_VERSION
from .recycle_bin import RECYCLE_BIN_SCHEMA_SQL


CORE_SCHEMA_SQL = """
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
    stop_reason TEXT NOT NULL DEFAULT '',
    route_index INTEGER NOT NULL DEFAULT 0,
    progress_fingerprint TEXT NOT NULL DEFAULT '',
    stalled_cycles INTEGER NOT NULL DEFAULT 0,
    last_progress_at TEXT NOT NULL DEFAULT '',
    last_recovery_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS autopilot_runs_project_idx
    ON autopilot_runs(project_root, created_at);
CREATE TABLE IF NOT EXISTS autopilot_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    at TEXT NOT NULL,
    data_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES autopilot_runs(run_id)
);
CREATE INDEX IF NOT EXISTS autopilot_events_run_idx
    ON autopilot_events(run_id, sequence);
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
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    project_root TEXT NOT NULL,
    role TEXT NOT NULL,
    runtime TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    controller_id TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    event_count INTEGER NOT NULL DEFAULT 0,
    last_event TEXT NOT NULL DEFAULT '',
    last_message TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    context_ledger_id TEXT NOT NULL DEFAULT '',
    context_ledger_digest TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS agent_sessions_project_idx
    ON agent_sessions(project_root, updated_at);
"""


FULL_SCHEMA_SQL = (
    CORE_SCHEMA_SQL
    + ASSET_TRANSACTION_SCHEMA_SQL
    + ASSET_REVISION_SCHEMA_SQL
    + RECYCLE_BIN_SCHEMA_SQL
    + CREATIVE_PLAN_SCHEMA_SQL
    + CREATIVE_PLAN_EVENT_SCHEMA_SQL
    + CONTEXT_LEDGER_SCHEMA_SQL
    + MUTATION_RECEIPT_SCHEMA_SQL
)


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the current schema and finish additive migrations atomically."""

    connection.executescript(FULL_SCHEMA_SQL)
    ensure_additive_columns(connection)
    connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")
