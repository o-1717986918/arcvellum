from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from literary_engineering_studio.jobs import JobStore
from literary_engineering_studio.supervisor import WorkerSupervisor


class DurableJobTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
