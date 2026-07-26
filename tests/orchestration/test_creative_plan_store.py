from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.jobs import JobStore

from tests.orchestration.plan_persistence_support import (
    FINGERPRINT,
    FailingCommitConnection,
    active_projection_args,
    index_record,
    persist_ready_record,
    record_digest,
)


class CreativePlanStoreTests(unittest.TestCase):
    def test_revision_identity_is_idempotent_but_digest_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            record = index_record("plan-persistence-one", project_root=root)

            reserved = store.reserve_creative_plan_revision(record)
            first = store.finalize_creative_plan_revision(
                reserved["plan_id"],
                reserved["revision"],
                digest=reserved["digest"],
            )
            repeated = store.reserve_creative_plan_revision(record)

            self.assertEqual(first, repeated)
            with self.assertRaisesRegex(ValueError, "conflicts"):
                store.reserve_creative_plan_revision({**record, "digest": "b" * 64})

    def test_status_and_ready_state_cannot_be_forged_by_low_level_callers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            active = index_record("plan-forged-active", project_root=root)
            active["status"] = "active"

            with self.assertRaisesRegex(ValueError, "machine-owned"):
                store.reserve_creative_plan_revision(active)

            missing = index_record(
                "plan-missing-artifacts",
                project_root=root,
                materialize=False,
            )
            reserved = store.reserve_creative_plan_revision(missing)
            with self.assertRaisesRegex(RuntimeError, "file is missing"):
                store.finalize_creative_plan_revision(
                    reserved["plan_id"],
                    reserved["revision"],
                    digest=reserved["digest"],
                )
            self.assertEqual(
                store.read_creative_plan_revision(
                    reserved["plan_id"],
                    reserved["revision"],
                )["artifact_state"],
                "reserved",
            )

    def test_activation_requires_current_revision_and_passing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            plan_id = "plan-activation-one"
            persist_ready_record(store, root, plan_id)
            active_args = active_projection_args(root, plan_id)

            with self.assertRaisesRegex(RuntimeError, "stale"):
                store.activate_creative_plan(
                    plan_id,
                    1,
                    expected_active_revision=0,
                    current_project_fingerprint="different",
                    verified_revision_digest=record_digest(plan_id),
                    **active_args,
                )
            active = store.activate_creative_plan(
                plan_id,
                1,
                expected_active_revision=0,
                current_project_fingerprint=FINGERPRINT,
                verified_revision_digest=record_digest(plan_id),
                **active_args,
            )
            self.assertEqual(active["active_revision"], 1)
            self.assertEqual(active["status"], "active")
            with self.assertRaisesRegex(RuntimeError, "changed concurrently"):
                store.activate_creative_plan(
                    plan_id,
                    1,
                    expected_active_revision=0,
                    current_project_fingerprint=FINGERPRINT,
                    verified_revision_digest=record_digest(plan_id),
                    **active_args,
                )

            pending_id = "plan-activation-pending"
            persist_ready_record(
                store,
                root,
                pending_id,
                review_status="pending",
            )
            with self.assertRaisesRegex(RuntimeError, "review"):
                store.activate_creative_plan(
                    pending_id,
                    1,
                    expected_active_revision=0,
                    current_project_fingerprint=FINGERPRINT,
                    verified_revision_digest=record_digest(pending_id),
                    **active_projection_args(root, pending_id),
                )

    def test_only_one_plan_can_be_active_for_a_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            for plan_id in ("plan-active-first", "plan-active-second"):
                persist_ready_record(store, root, plan_id)
            _activate(store, root, "plan-active-first")
            _activate(store, root, "plan-active-second")

            self.assertEqual(
                store.read_creative_plan("plan-active-first")["status"],
                "superseded",
            )
            self.assertEqual(
                store.read_creative_plan("plan-active-second")["status"],
                "active",
            )
            projection = _read_projection(root)
            self.assertEqual(projection["plan_id"], "plan-active-second")

    def test_concurrent_activation_keeps_index_and_projection_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            database = Path(temporary) / "studio.sqlite3"
            first_store = JobStore(database)
            second_store = JobStore(database)
            for plan_id in ("plan-race-first", "plan-race-second"):
                persist_ready_record(first_store, root, plan_id)

            with ThreadPoolExecutor(max_workers=2) as pool:
                completed = tuple(
                    pool.map(
                        lambda pair: _activate(*pair),
                        (
                            (first_store, root, "plan-race-first"),
                            (second_store, root, "plan-race-second"),
                        ),
                    )
                )

            self.assertEqual(set(completed), {"plan-race-first", "plan-race-second"})
            plans = first_store.list_creative_plans(str(root))
            active = [item for item in plans if item["status"] == "active"]
            self.assertEqual(len(active), 1)
            self.assertEqual(_read_projection(root)["plan_id"], active[0]["plan_id"])

    def test_activation_event_failure_rolls_back_index_and_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            plan_id = "plan-activation-rollback"
            persist_ready_record(store, root, plan_id)

            with patch(
                "literary_engineering_studio.persistence.creative_plan_activation."
                "append_creative_plan_event_tx",
                side_effect=RuntimeError("activation event failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "activation event failed"):
                    _activate(store, root, plan_id)

            self.assertEqual(store.read_creative_plan(plan_id)["status"], "shadow")
            self.assertFalse(_projection_path(root).exists())

    def test_commit_failure_rolls_back_index_and_active_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            plan_id = "plan-commit-rollback"
            persist_ready_record(store, root, plan_id)
            connection = FailingCommitConnection(store._connect())

            with patch.object(store, "_connect", return_value=connection):
                with self.assertRaisesRegex(sqlite3.OperationalError, "commit failed"):
                    _activate(store, root, plan_id)

            self.assertEqual(store.read_creative_plan(plan_id)["status"], "shadow")
            self.assertFalse(_projection_path(root).exists())

    def test_plan_and_event_write_roll_back_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "work"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            with patch(
                "literary_engineering_studio.persistence.creative_plans."
                "append_creative_plan_event_tx",
                side_effect=RuntimeError("event failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "event failed"):
                    store.reserve_creative_plan_revision(
                        index_record("plan-rollback-one", project_root=root)
                    )

            with self.assertRaises(FileNotFoundError):
                store.read_creative_plan("plan-rollback-one")

    def test_schema_eleven_migrates_with_backup_and_creative_plan_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE legacy (value TEXT);
                INSERT INTO legacy VALUES ('keep');
                PRAGMA user_version = 11;
                """
            )
            connection.commit()
            connection.close()

            store = JobStore(database)

            self.assertIsNotNone(store.migration_backup)
            with store._connection() as migrated:
                tables = {
                    str(row["name"])
                    for row in migrated.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                value = migrated.execute("SELECT value FROM legacy").fetchone()["value"]
            self.assertEqual(value, "keep")
            self.assertTrue(
                {
                    "creative_plans",
                    "creative_plan_revisions",
                    "creative_plan_events",
                }.issubset(tables)
            )


def _activate(store: JobStore, root: Path, plan_id: str) -> str:
    store.activate_creative_plan(
        plan_id,
        1,
        expected_active_revision=0,
        current_project_fingerprint=FINGERPRINT,
        verified_revision_digest=record_digest(plan_id),
        **active_projection_args(root, plan_id),
    )
    return plan_id


def _projection_path(root: Path) -> Path:
    return root / "workflow" / "orchestration" / "active_plan.json"


def _read_projection(root: Path) -> dict:
    return json.loads(_projection_path(root).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
