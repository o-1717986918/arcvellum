"""Architecture regressions for explicit persistence composition."""

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.persistence.autopilot_runs import AutopilotRepository
from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.persistence.sessions import SessionRepository
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork


class PersistenceCompositionTests(unittest.TestCase):
    def test_job_store_composes_autopilot_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")

            self.assertIsInstance(store.autopilot_runs, AutopilotRepository)
            self.assertNotIsInstance(store, AutopilotRepository)
            run = store.create_autopilot_run(
                temporary,
                mode="collaborative",
                runtime="test-runtime",
                policy={"mode": "collaborative"},
            )

            self.assertEqual(run["status"], "running")
            self.assertEqual(store.read_autopilot_run(run["run_id"])["runtime"], "test-runtime")

    def test_job_store_composes_session_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")

            self.assertIsInstance(store.sessions, SessionRepository)
            self.assertNotIsInstance(store, SessionRepository)
            session = store.create_advisor_session(temporary, "snapshot-01")
            store.append_advisor_message(session["session_id"], "user", {"text": "继续"})

            restored = store.read_advisor_session(session["session_id"])
            self.assertEqual(restored["messages"][0]["payload"]["text"], "继续")

    def test_unit_of_work_rolls_back_failed_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "unit.sqlite3"
            uow = SqliteUnitOfWork(path)
            with uow.write() as connection:
                connection.execute("CREATE TABLE entries (value TEXT NOT NULL)")

            with self.assertRaises(RuntimeError):
                with uow.write(immediate=True) as connection:
                    connection.execute("INSERT INTO entries (value) VALUES ('discarded')")
                    raise RuntimeError("abort")

            with uow.read() as connection:
                count = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
