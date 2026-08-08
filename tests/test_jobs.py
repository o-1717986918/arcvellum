from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.supervisor import WorkerSupervisor
from literary_engineering_studio.runtime.execution_admission import ExecutionAdmission
from literary_engineering_studio.runtime.resources import ResourceClaim, project_identity


class DurableJobTests(unittest.TestCase):
    def test_create_rolls_back_job_when_initial_event_write_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            with patch.object(store, "_append_event_tx", side_effect=RuntimeError("event write failed")):
                with self.assertRaisesRegex(RuntimeError, "event write failed"):
                    store.create({"project_root": "work"})

            with store._connection() as connection:
                count = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
            self.assertEqual(count, 0)

    def test_claim_rolls_back_status_when_started_event_write_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": "work"})
            with patch.object(store, "_append_event_tx", side_effect=RuntimeError("event write failed")):
                with self.assertRaisesRegex(RuntimeError, "event write failed"):
                    store.claim(job["job_id"], "worker-one")

            self.assertEqual(store.read(job["job_id"])["status"], "queued")
            self.assertEqual(store.events_since(job["job_id"])[-1]["event"], "run.queued")

    def test_project_lock_rolls_back_when_lock_event_write_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": "work"})
            with patch.object(store, "_append_event_tx", side_effect=RuntimeError("event write failed")):
                with self.assertRaisesRegex(RuntimeError, "event write failed"):
                    store.acquire_lock("project:work:route:scene", job["job_id"], "worker-one")

            with store._connection() as connection:
                count = connection.execute("SELECT COUNT(*) AS count FROM project_locks").fetchone()["count"]
            self.assertEqual(count, 0)

    def test_database_migration_creates_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE legacy (value TEXT)")
            connection.execute("INSERT INTO legacy VALUES ('keep')")
            connection.commit()
            connection.close()
            store = JobStore(database)
            self.assertIsNotNone(store.migration_backup)
            self.assertTrue(store.migration_backup.is_file())
            self.assertTrue(store.health()["ready"])

    def test_jobs_events_idempotency_and_restart_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            store = JobStore(database)
            first = store.create({"project_root": "work", "route": "scene-development"}, idempotency_key="same")
            duplicate = store.create({"project_root": "other"}, idempotency_key="same")
            self.assertEqual(first["job_id"], duplicate["job_id"])
            self.assertEqual(store.events_since(first["job_id"])[0]["event"], "run.queued")
            self.assertTrue(store.claim(first["job_id"], "worker-one"))

            restarted = JobStore(database)
            recovered = restarted.recover_interrupted()
            self.assertEqual(recovered, [first["job_id"]])
            self.assertEqual(restarted.read(first["job_id"])["status"], "interrupted")
            self.assertEqual(restarted.events_since(first["job_id"])[-1]["event"], "run.interrupted")

    def test_project_lock_rejects_competing_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            first = store.create({})
            second = store.create({})
            self.assertTrue(store.acquire_lock("project:a:route:b", first["job_id"], "one"))
            self.assertFalse(store.acquire_lock("project:a:route:b", second["job_id"], "two"))
            store.release_lock("project:a:route:b", first["job_id"])
            self.assertTrue(store.acquire_lock("project:a:route:b", second["job_id"], "two"))

    def test_agent_session_updates_preserve_identity_and_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            created = store.upsert_agent_session(
                "session-123456",
                project_root="C:/work",
                role="worker",
                runtime="opencode",
                model="provider/model",
                status="running",
                task_id="task-1",
                route="scene-development",
                controller_id="run-1",
                last_event="runner.session.started",
            )
            updated = store.upsert_agent_session(
                "session-123456",
                project_root="",
                role="",
                runtime="",
                status="complete",
                last_event="runner.session.finished",
            )
            self.assertEqual(updated["model"], "provider/model")
            self.assertEqual(updated["task_id"], "task-1")
            self.assertEqual(updated["controller_id"], "run-1")
            self.assertEqual(updated["event_count"], created["event_count"] + 1)
            self.assertTrue(updated["finished_at"])

    def test_autopilot_lease_and_progress_are_cross_store_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            first = JobStore(database)
            policy = {"mode": "supervised_auto"}
            run = first.create_autopilot_run("C:/work", mode="supervised_auto", runtime="opencode", policy=policy)
            second = JobStore(database)

            self.assertTrue(first.acquire_autopilot_lease(run["run_id"], "controller-a"))
            self.assertFalse(second.acquire_autopilot_lease(run["run_id"], "controller-b"))
            self.assertTrue(first.renew_autopilot_lease(run["run_id"], "controller-a"))
            first.advance_autopilot_run(run["run_id"], failures=0, last_error="")
            second.advance_autopilot_run(run["run_id"], failures=0, last_error="")
            self.assertEqual(second.read_autopilot_run(run["run_id"])["tasks_completed"], 2)
            first.release_autopilot_lease(run["run_id"], "controller-a")
            self.assertTrue(second.acquire_autopilot_lease(run["run_id"], "controller-b"))

    def test_schema_eight_migrates_autopilot_progress_and_agent_sessions(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE autopilot_runs (
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
                INSERT INTO autopilot_runs (
                    run_id, project_root, mode, runtime, status, policy_json,
                    created_at, updated_at, started_at
                ) VALUES (
                    'autopilot-legacy1234', 'C:/work', 'supervised_auto',
                    'opencode', 'running', '{"mode":"supervised_auto"}',
                    '2026-07-23T00:00:00+00:00',
                    '2026-07-23T00:00:00+00:00',
                    '2026-07-23T00:00:00+00:00'
                );
                PRAGMA user_version = 7;
                """
            )
            connection.commit()
            connection.close()
            restarted = JobStore(database)
            run = restarted.read_autopilot_run("autopilot-legacy1234")
            self.assertEqual(run["route_index"], 0)
            self.assertEqual(run["progress_fingerprint"], "")
            updated = restarted.update_autopilot_run(
                run["run_id"],
                route_index=3,
                progress_fingerprint="fingerprint-one",
                stalled_cycles=2,
                last_progress_at="2026-07-23T12:00:00+00:00",
            )
            self.assertEqual(updated["route_index"], 3)
            self.assertEqual(updated["progress_fingerprint"], "fingerprint-one")
            self.assertEqual(updated["stalled_cycles"], 2)

            session = restarted.upsert_agent_session(
                "ses_worker_001",
                project_root="C:/work",
                role="worker",
                runtime="opencode",
                model="provider/model",
                task_id="scene-generate",
                route="scene-development",
                last_event="runner.session.started",
            )
            self.assertEqual(session["status"], "running")
            self.assertEqual(session["event_count"], 1)
            finished = restarted.upsert_agent_session(
                "ses_worker_001",
                project_root="C:/work",
                role="worker",
                runtime="opencode",
                model="provider/model",
                status="complete",
                task_id="scene-generate",
                route="scene-development",
                last_event="runner.session.completed",
            )
            self.assertTrue(finished["finished_at"])
            self.assertEqual(finished["event_count"], 2)
            self.assertEqual(
                [item["session_id"] for item in restarted.list_agent_sessions("C:/work")],
                ["ses_worker_001"],
            )

    def test_schema_fifteen_preserves_context_ledgers_and_adds_mutation_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            first = JobStore(database)
            first.upsert_agent_session(
                "session-before-ledger",
                project_root="C:/work",
                role="worker",
                runtime="opencode",
            )
            connection = sqlite3.connect(database)
            try:
                connection.execute("ALTER TABLE agent_sessions DROP COLUMN context_ledger_id")
                connection.execute("ALTER TABLE agent_sessions DROP COLUMN context_ledger_digest")
                connection.execute("DROP TABLE context_ledger_entries")
                connection.execute("DROP TABLE context_ledgers")
                connection.execute("PRAGMA user_version = 12")
                connection.commit()
            finally:
                connection.close()

            restarted = JobStore(database)
            self.assertIsNotNone(restarted.migration_backup)
            self.assertEqual(restarted.health()["schema_version"], 16)
            session = restarted.read_agent_session("session-before-ledger")
            self.assertEqual(session["context_ledger_id"], "")
            self.assertEqual(session["context_ledger_digest"], "")
            with restarted._connection() as connection:
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            self.assertIn("context_ledgers", tables)
            self.assertIn("context_ledger_entries", tables)
            self.assertIn("mutation_receipts", tables)

    def test_schema_fifteen_adds_execution_context_columns_to_existing_ledgers(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            JobStore(database)
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "ALTER TABLE context_ledgers DROP COLUMN execution_context_digest"
                )
                connection.execute(
                    "ALTER TABLE context_ledger_entries DROP COLUMN visibility_tier"
                )
                connection.execute("PRAGMA user_version = 14")
                connection.commit()
            finally:
                connection.close()

            restarted = JobStore(database)

            self.assertEqual(restarted.health()["schema_version"], 16)
            with restarted._connection() as connection:
                ledger_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(context_ledgers)"
                    ).fetchall()
                }
                entry_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(context_ledger_entries)"
                    ).fetchall()
                }
            self.assertIn("execution_context_digest", ledger_columns)
            self.assertIn("visibility_tier", entry_columns)

    def test_supervisor_persists_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": "work"})
            supervisor = WorkerSupervisor(store, max_workers=1, lease_seconds=30)
            supervisor.submit(
                job["job_id"],
                lambda _cancel: {"status": "complete", "message": "done"},
                lock_key="project:test:route:test",
            )
            deadline = time.time() + 5
            while time.time() < deadline and store.read(job["job_id"])["status"] in {"queued", "running"}:
                time.sleep(0.02)
            completed = store.read(job["job_id"])
            supervisor.shutdown()
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(completed["result"]["message"], "done")
            event_names = [item["event"] for item in store.events_since(job["job_id"])]
            self.assertIn("lock.acquired", event_names)
            self.assertIn("run.complete", event_names)
            self.assertIn("lock.released", event_names)

    def test_supervisor_allows_two_explicit_read_only_claims(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "work"
            project.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            first = store.create({"project_root": str(project)})
            second = store.create({"project_root": str(project)})
            supervisor = WorkerSupervisor(store, max_workers=2, lease_seconds=30)
            first_started = threading.Event()
            second_started = threading.Event()
            release = threading.Event()

            def run(first_event, other_event):
                first_event.set()
                if not other_event.wait(3):
                    return {"status": "failed", "message": "peer did not start"}
                release.wait(3)
                return {"status": "complete", "message": "shared read complete"}

            supervisor.submit(
                first["job_id"],
                lambda _cancel: run(first_started, second_started),
                lock_key="legacy-project-lock",
                resource_claim=_read_claim(project, "reader-a", "canon/a.yaml"),
            )
            supervisor.submit(
                second["job_id"],
                lambda _cancel: run(second_started, first_started),
                lock_key="legacy-project-lock",
                resource_claim=_read_claim(project, "reader-b", "canon/a.yaml"),
            )

            self.assertTrue(first_started.wait(3))
            self.assertTrue(second_started.wait(3))
            release.set()
            _wait_for_jobs(store, (first["job_id"], second["job_id"]))
            supervisor.shutdown()

            self.assertEqual(store.read(first["job_id"])["status"], "complete")
            self.assertEqual(store.read(second["job_id"])["status"], "complete")
            self.assertEqual(store.list_resource_leases(), [])

    def test_supervisor_read_only_fast_path_rejects_write_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "work"
            project.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": str(project)})
            supervisor = WorkerSupervisor(store, max_workers=1, lease_seconds=30)
            claim = ResourceClaim(
                task_node_id="writer",
                project_id=project_identity(project),
                reads=(),
                writes=("drafts/scenes/scene_0001.md",),
                runtime_slot="agent-worker",
                model_slot="default",
                network="none",
                exclusive_barriers=(),
            )

            supervisor.submit(
                job["job_id"],
                lambda _cancel: {"status": "complete"},
                lock_key="legacy-project-lock",
                resource_claim=claim,
            )
            _wait_for_jobs(store, (job["job_id"],))
            supervisor.shutdown()

            failed = store.read(job["job_id"])
            self.assertEqual(failed["status"], "failed")
            self.assertIn("read-only claims only", failed["error"])

    def test_execution_heartbeat_renews_job_and_project_lock_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": "work"})
            worker = "worker-one"
            lock_key = "project:test:execution"
            self.assertTrue(store.claim(job["job_id"], worker, lease_seconds=30))
            self.assertTrue(
                store.acquire_lock(lock_key, job["job_id"], worker, lease_seconds=30)
            )
            before = store.read(job["job_id"])["lease_expires_at"]

            store.heartbeat_execution(
                job["job_id"], worker, lock_key, lease_seconds=90
            )

            after = store.read(job["job_id"])["lease_expires_at"]
            self.assertGreater(after, before)
            with store._connection() as connection:
                lock = connection.execute(
                    "SELECT lease_expires_at FROM project_locks WHERE lock_key = ?",
                    (lock_key,),
                ).fetchone()
            self.assertIsNotNone(lock)
            self.assertGreater(str(lock["lease_expires_at"]), after)

            with store._connection() as connection:
                connection.execute(
                    "DELETE FROM project_locks WHERE lock_key = ?", (lock_key,)
                )
            unchanged = store.read(job["job_id"])["heartbeat_at"]
            with self.assertRaisesRegex(RuntimeError, "project execution lease"):
                store.heartbeat_execution(
                    job["job_id"], worker, lock_key, lease_seconds=90
                )
            self.assertEqual(store.read(job["job_id"])["heartbeat_at"], unchanged)

    def test_supervisor_rejects_missing_status_instead_of_reporting_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            job = store.create({"project_root": "work"})
            supervisor = WorkerSupervisor(store, max_workers=1, lease_seconds=30)
            supervisor.submit(
                job["job_id"],
                lambda _cancel: {"message": "forgot status"},
                lock_key="project:test:missing-status",
            )
            deadline = time.time() + 5
            while time.time() < deadline and store.read(job["job_id"])["status"] in {"queued", "running"}:
                time.sleep(0.02)
            failed = store.read(job["job_id"])
            supervisor.shutdown()

            self.assertEqual(failed["status"], "failed")
            self.assertIn("must declare status", failed["error"])

    def test_supervisor_cancels_execution_when_project_lease_is_lost(self):
        class ImmediateHeartbeat:
            def wait(self, timeout):
                return False

        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            supervisor = WorkerSupervisor(store, max_workers=1, lease_seconds=30)
            cancel = threading.Event()
            with patch.object(
                store,
                "heartbeat_execution",
                side_effect=RuntimeError("project lease lost"),
            ):
                supervisor._heartbeat_loop(
                    ExecutionAdmission(
                        project_root="work",
                        coordinator_owner="job-lease-test",
                        job_id="job-lease-test",
                        lock_key="project:test:execution",
                    ),
                    ImmediateHeartbeat(),
                    cancel,
                )
            supervisor.shutdown()

            self.assertTrue(cancel.is_set())
            self.assertIn(
                "project lease lost",
                str(getattr(cancel, "_arcvellum_execution_lease_error", "")),
            )


def _read_claim(project: Path, node_id: str, path: str) -> ResourceClaim:
    return ResourceClaim(
        task_node_id=node_id,
        project_id=project_identity(project),
        reads=(path,),
        writes=(),
        runtime_slot="agent-worker",
        model_slot="default",
        network="none",
        exclusive_barriers=(),
    )


def _wait_for_jobs(store: JobStore, job_ids: tuple[str, ...]) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        if all(
            store.read(job_id)["status"] not in {"queued", "running"}
            for job_id in job_ids
        ):
            return
        time.sleep(0.02)


if __name__ == "__main__":
    unittest.main()
